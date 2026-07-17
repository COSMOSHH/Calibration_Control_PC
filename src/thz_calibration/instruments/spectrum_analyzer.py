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

    def configure_sweep_for_frequency(self, frequency_ghz: float) -> None:
        ...


def _mapped_sweep_range_ghz(
    frequency_ghz: float,
    span_ghz: float,
    frequency_divisor: float = 1.0,
) -> tuple[float, float]:
    if frequency_ghz <= 0:
        raise ValueError("spectrum analyzer center frequency must be positive")
    if span_ghz <= 0:
        raise ValueError("spectrum analyzer span must be positive")
    if frequency_divisor <= 0:
        raise ValueError("spectrum analyzer frequency divisor must be positive")
    return (frequency_ghz / frequency_divisor, span_ghz / frequency_divisor)


def _sweep_range_ghz(
    context: MeasurementContext | None,
    span_ghz: float,
    frequency_divisor: float = 1.0,
) -> tuple[float, float] | None:
    if context is None:
        return None
    return _mapped_sweep_range_ghz(context.frequency_ghz, span_ghz, frequency_divisor)


def _sweep_range_commands(sweep_range_ghz: tuple[float, float]) -> tuple[str, str]:
    center_ghz, span_ghz = sweep_range_ghz
    center_hz = center_ghz * 1e9
    span_hz = span_ghz * 1e9
    return (
        f"SENSe:FREQuency:CENTer {center_hz:.12g}",
        f"SENSe:FREQuency:SPAN {span_hz:.12g}",
    )


def _safe_list_visa_resources(resource_manager) -> tuple[str, ...]:
    try:
        return tuple(str(resource) for resource in resource_manager.list_resources())
    except Exception:
        return ()


def _visa_resource_candidates(address: str) -> tuple[str, ...]:
    candidates = [address]
    parts = address.split("::")
    if len(parts) >= 3 and parts[0].upper().startswith("TCPIP") and parts[-1].upper() in ("INSTR", "SOCKET"):
        board = parts[0]
        host = parts[1]
        board0 = "TCPIP0" if board.upper() == "TCPIP" else board
        if parts[-1].upper() == "INSTR" and len(parts) == 3:
            candidates.extend(
                [
                    f"{board0}::{host}::inst0::INSTR",
                    f"{board0}::{host}::INSTR",
                    f"{board}::{host}::inst0::INSTR",
                ]
            )
        elif parts[-1].upper() == "INSTR" and len(parts) == 4:
            if board != board0:
                candidates.append(f"{board0}::{host}::{parts[2]}::INSTR")
            if parts[2].lower() != "inst0":
                candidates.append(f"{board0}::{host}::inst0::INSTR")
        if not any(candidate.upper().endswith("::HISLIP0::INSTR") for candidate in candidates):
            candidates.append(f"{board0}::{host}::hislip0::INSTR")
        if not any(candidate.upper().endswith("::5025::SOCKET") for candidate in candidates):
            candidates.append(f"{board0}::{host}::5025::SOCKET")
    return tuple(dict.fromkeys(candidates))


def _try_open_visa_resource(resource_manager, address: str):
    errors: list[tuple[str, Exception]] = []
    for candidate in _visa_resource_candidates(address):
        try:
            return candidate, resource_manager.open_resource(candidate), errors
        except Exception as exc:
            errors.append((candidate, exc))
    return "", None, errors


def _format_visa_open_error(address: str, errors: list[tuple[str, Exception]], resources: tuple[str, ...]) -> str:
    last_error = errors[-1][1] if errors else "unknown error"
    lines = [
        f"连接频谱仪 VISA 资源失败：{address}",
        "已尝试资源名：" + ", ".join(candidate for candidate, _ in errors),
        f"最后错误：{last_error}",
    ]
    if resources:
        lines.append("当前可见 VISA 资源：" + ", ".join(resources))
    else:
        lines.append("当前 ResourceManager 未列出任何 VISA 资源。")
    lines.append("ping 通只代表 IP 可达；请在 NI MAX/Keysight Connection Expert 中确认 VXI-11/HiSLIP/Socket 服务和完整资源名。")
    return "\n".join(lines)


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

    def configure_sweep_for_frequency(self, frequency_ghz: float) -> None:
        """模拟频谱仪不需要下发扫频设置，但保留接口供 UI 统一调用。"""
        if frequency_ghz <= 0:
            raise ValueError("spectrum analyzer center frequency must be positive")


class VisaSpectrumAnalyzer:
    """真实频谱仪 VISA/SCPI 访问实现。

    当前只实现“寻找最大 marker 并读取 Y 值”的最小闭环。如果换仪器型号或 SCPI
    命令不兼容，优先修改 read_peak_power_dbm()。
    """

    def __init__(
        self,
        address: str,
        timeout_ms: int = 5000,
        sweep_span_ghz: float = 1.0,
        frequency_divisor: float = 1.0,
    ) -> None:
        self.address = address
        self.timeout_ms = timeout_ms
        self.sweep_span_ghz = sweep_span_ghz
        self.frequency_divisor = frequency_divisor
        self._rm = None
        self._instrument = None
        self._last_sweep_range_ghz: tuple[float, float] | None = None

    def connect(self) -> None:
        """创建 pyvisa ResourceManager 并打开指定资源。"""
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required for VISA spectrum analyzer access") from exc

        self._rm = pyvisa.ResourceManager()
        opened_address, instrument, errors = _try_open_visa_resource(self._rm, self.address)
        if instrument is None:
            resources = _safe_list_visa_resources(self._rm)
            self.disconnect()
            last_error = errors[-1][1] if errors else RuntimeError("unknown VISA open error")
            raise RuntimeError(_format_visa_open_error(self.address, errors, resources)) from last_error
        self.address = opened_address
        self._instrument = instrument
        self._instrument.timeout = self.timeout_ms
        if self.address.upper().endswith("::SOCKET"):
            self._instrument.write_termination = "\n"
            self._instrument.read_termination = "\n"
        self._last_sweep_range_ghz = None

    def disconnect(self) -> None:
        """关闭仪器和资源管理器，避免 VISA 句柄泄漏。"""
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None
        self._last_sweep_range_ghz = None

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

        context 中的 frequency_ghz 用于在读数前把频谱仪扫频范围设置到目标频率附近。
        """
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
        self._configure_sweep_range(context)
        self._instrument.write("CALCulate:MARKer1:MAXimum")
        time.sleep(0.1)
        return float(self._instrument.query("CALCulate:MARKer1:Y?"))

    def configure_sweep_for_frequency(self, frequency_ghz: float) -> None:
        """按当前校准频率主动同步频谱仪观察中心频率。"""
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
        self._configure_sweep_range_for_frequency(frequency_ghz)

    def _configure_sweep_range(self, context: MeasurementContext | None) -> None:
        sweep_range = _sweep_range_ghz(context, self.sweep_span_ghz, self.frequency_divisor)
        if sweep_range is None or sweep_range == self._last_sweep_range_ghz:
            return
        self._write_sweep_range(sweep_range)

    def _configure_sweep_range_for_frequency(self, frequency_ghz: float) -> None:
        sweep_range = _mapped_sweep_range_ghz(frequency_ghz, self.sweep_span_ghz, self.frequency_divisor)
        if sweep_range == self._last_sweep_range_ghz:
            return
        self._write_sweep_range(sweep_range)

    def _write_sweep_range(self, sweep_range: tuple[float, float]) -> None:
        for command in _sweep_range_commands(sweep_range):
            self._instrument.write(command)
        self._last_sweep_range_ghz = sweep_range
        time.sleep(0.1)


class XianGpibSpectrumAnalyzer:
    """西安研究所已验证的 R&S FSQ40 GPIB/VISA/SCPI 访问实现。

    这套逻辑移植自 `转台控制` 工程，保留其单次扫描、峰值搜索和 FSQ 型号识别流程。
    """

    def __init__(
        self,
        address: str,
        timeout_ms: int = 10000,
        sweep_span_ghz: float = 1.0,
        frequency_divisor: float = 1.0,
    ) -> None:
        self.address = address
        self.timeout_ms = timeout_ms
        self.sweep_span_ghz = sweep_span_ghz
        self.frequency_divisor = frequency_divisor
        self._rm = None
        self._instrument = None
        self._connected = False
        self._last_sweep_range_ghz: tuple[float, float] | None = None

    def connect(self) -> None:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required for VISA spectrum analyzer access") from exc

        self._rm = pyvisa.ResourceManager()
        opened_address, instrument, errors = _try_open_visa_resource(self._rm, self.address)
        if instrument is None:
            resources = _safe_list_visa_resources(self._rm)
            self.disconnect()
            last_error = errors[-1][1] if errors else RuntimeError("unknown VISA open error")
            raise RuntimeError(_format_visa_open_error(self.address, errors, resources)) from last_error

        try:
            self.address = opened_address
            self._instrument = instrument
            self._instrument.timeout = self.timeout_ms
            self._instrument.write_termination = "\n"
            self._instrument.read_termination = "\n"
            self._last_sweep_range_ghz = None

            identity = self.read_identity()
            if "FSQ" not in identity.upper():
                raise RuntimeError(f"connected VISA resource is not an FSQ analyzer: {identity}")

            self._write("INIT:CONT OFF")
            self._write("CALC:MARK ON")
            self._connected = True
        except Exception as exc:
            resources = _safe_list_visa_resources(self._rm)
            self.disconnect()
            if isinstance(exc, RuntimeError) and "connected VISA resource is not an FSQ analyzer" in str(exc):
                raise
            visible = ", ".join(resources) if resources else "当前 ResourceManager 未列出任何 VISA 资源。"
            raise RuntimeError(f"频谱仪 VISA 资源已打开，但初始化失败：{self.address}\n原始错误：{exc}\n当前可见 VISA 资源：{visible}") from exc

    def disconnect(self) -> None:
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None
        self._connected = False
        self._last_sweep_range_ghz = None

    def is_connected(self) -> bool:
        return self._connected and self._instrument is not None

    def read_identity(self) -> str:
        return self._query("*IDN?").strip()

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        """按西安所现有流程执行单次扫频并读取峰值功率。"""
        self._ensure_connected()
        self._write("INIT:CONT OFF")
        self._configure_sweep_range(context)
        self._write("INIT")
        self._query("*OPC?")
        self._write("CALC:MARK:MAX")
        return float(self._query("CALC:MARK:Y?"))

    def configure_sweep_for_frequency(self, frequency_ghz: float) -> None:
        self._ensure_connected()
        self._configure_sweep_range_for_frequency(frequency_ghz)

    def _configure_sweep_range(self, context: MeasurementContext | None) -> None:
        sweep_range = _sweep_range_ghz(context, self.sweep_span_ghz, self.frequency_divisor)
        if sweep_range is None or sweep_range == self._last_sweep_range_ghz:
            return
        self._write_sweep_range(sweep_range)

    def _configure_sweep_range_for_frequency(self, frequency_ghz: float) -> None:
        sweep_range = _mapped_sweep_range_ghz(frequency_ghz, self.sweep_span_ghz, self.frequency_divisor)
        if sweep_range == self._last_sweep_range_ghz:
            return
        self._write_sweep_range(sweep_range)

    def _write_sweep_range(self, sweep_range: tuple[float, float]) -> None:
        for command in _sweep_range_commands(sweep_range):
            self._write(command)
        self._last_sweep_range_ghz = sweep_range

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
