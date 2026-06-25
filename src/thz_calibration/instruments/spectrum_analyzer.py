from __future__ import annotations

import math
import random
import time
from typing import Protocol

from ..models import MeasurementContext
from ..utils import dbm_to_uw, uw_to_dbm


class SpectrumAnalyzer(Protocol):
    """频谱仪抽象接口。

    CalibrationEngine 只依赖这个接口，因此 UI0 可以在 simulated 和 VISA 实机之间
    切换，而不影响扫描主流程。
    """

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def read_identity(self) -> str:
        ...

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        ...


class SimulatedSpectrumAnalyzer:
    """无频谱仪时使用的模拟读数源。

    模拟器会给每个目标馈源设置一个“理想相位”，扫描到接近该相位时功率更高。
    这样 UI0 的扫描、最佳点选择、Excel 标红都能在没有仪器的情况下验证。
    """

    def __init__(self, address: str = "SIMULATED") -> None:
        self.address = address
        self._connected = False
        # 固定随机种子保证调试时每次运行的模拟曲线大致一致。
        self._rng = random.Random(504)

    def connect(self) -> None:
        """模拟连接成功。"""
        self._connected = True

    def disconnect(self) -> None:
        """模拟断开连接。"""
        self._connected = False

    def is_connected(self) -> bool:
        """返回模拟连接状态。"""
        return self._connected

    def read_identity(self) -> str:
        """返回类似 *IDN? 的设备身份字符串。"""
        return "SIMULATED,THZ-SPECTRUM,0000,0.1"

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        """返回一个模拟峰值功率。

        context 为空时返回普通噪声读数；有 context 时按当前扫描相位与理想相位的
        接近程度生成相干增强效果。
        """
        if not self._connected:
            raise RuntimeError("simulated spectrum analyzer is not connected")

        if context is None:
            return -20.0 + self._rng.uniform(-0.2, 0.2)

        ideal_phase = {
            1: 0.0,
            2: 112.5,
            3: 202.5,
            4: 281.25,
        }.get(context.target_feed_id, 0.0)
        # 用 cos 曲线模拟相位接近最佳点时功率升高，范围归一化到 0~1。
        delta_rad = math.radians((context.phase_deg - ideal_phase) % 360.0)
        coherence = (1.0 + math.cos(delta_rad)) / 2.0
        # 打开的馈源越多，基础功率越高，便于模拟逐步加入馈源的校准流程。
        active_count = sum(1 for feed in context.feed_states if feed.enabled)
        baseline_uw = 16.0 * max(active_count, 1)
        power_uw = baseline_uw * (0.35 + 0.65 * coherence)
        noise_uw = self._rng.uniform(-0.35, 0.35)
        return uw_to_dbm(max(power_uw + noise_uw, 0.001))


class VisaSpectrumAnalyzer:
    """真实频谱仪 VISA/SCPI 访问实现。

    当前只实现“寻找最大 marker 并读取 Y 值”的最小闭环。如果换仪器型号或 SCPI
    命令不兼容，优先修改 read_peak_power_dbm()。
    """

    def __init__(self, address: str, timeout_ms: int = 5000) -> None:
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm = None
        self._instrument = None

    def connect(self) -> None:
        """创建 pyvisa ResourceManager 并打开指定资源。"""
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required for VISA spectrum analyzer access") from exc

        self._rm = pyvisa.ResourceManager()
        self._instrument = self._rm.open_resource(self.address)
        self._instrument.timeout = self.timeout_ms

    def disconnect(self) -> None:
        """关闭仪器和资源管理器，避免 VISA 句柄泄漏。"""
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None

    def is_connected(self) -> bool:
        """VISA 资源对象存在即认为已连接。"""
        return self._instrument is not None

    def read_identity(self) -> str:
        """读取仪器 *IDN?，用于联调时确认连接的是目标设备。"""
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
        return self._instrument.query("*IDN?").strip()

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        """让 marker 跳到当前最大峰值，并读取 marker Y 值。

        context 当前不参与真实仪器命令，只作为接口兼容保留。
        """
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
        self._instrument.write("CALCulate:MARKer1:MAXimum")
        time.sleep(0.1)
        return float(self._instrument.query("CALCulate:MARKer1:Y?"))


class XianGpibSpectrumAnalyzer:
    """西安研究所已验证的 R&S FSQ40 GPIB/VISA/SCPI 访问实现。

    这套逻辑移植自 `转台控制` 工程，保留其单次扫描、峰值搜索和 FSQ 型号识别流程。
    """

    def __init__(self, address: str, timeout_ms: int = 10000) -> None:
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm = None
        self._instrument = None
        self._connected = False

    def connect(self) -> None:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required for VISA spectrum analyzer access") from exc

        self._rm = pyvisa.ResourceManager()
        self._instrument = self._rm.open_resource(self.address)
        self._instrument.timeout = self.timeout_ms
        self._instrument.write_termination = "\n"
        self._instrument.read_termination = "\n"

        identity = self.read_identity()
        if "FSQ" not in identity.upper():
            raise RuntimeError(f"connected VISA resource is not an FSQ analyzer: {identity}")

        self._write("INIT:CONT OFF")
        self._write("CALC:MARK ON")
        self._connected = True

    def disconnect(self) -> None:
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._instrument is not None

    def read_identity(self) -> str:
        return self._query("*IDN?").strip()

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        """按西安所现有流程执行单次扫频并读取峰值功率。"""
        self._ensure_connected()
        self._write("INIT:CONT OFF")
        self._write("INIT")
        self._query("*OPC?")
        self._write("CALC:MARK:MAX")
        return float(self._query("CALC:MARK:Y?"))

    def _write(self, command: str) -> None:
        self._ensure_instrument()
        self._instrument.write(command)

    def _query(self, command: str) -> str:
        self._ensure_instrument()
        return str(self._instrument.query(command))

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Xi'an GPIB spectrum analyzer is not connected")

    def _ensure_instrument(self) -> None:
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
