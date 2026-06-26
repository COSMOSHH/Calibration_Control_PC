from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# 项目根路径统一从当前文件向上推导，避免在不同启动目录下找不到 docs/output。
ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs"
TEMPLATE_DIR = DOCS_DIR / "馈源间相位校准数据保存格式"
OUTPUT_DIR = ROOT_DIR / "output"
FREQUENCY_PLAN_PATH = DOCS_DIR / "说明文档" / "中频和本振频率核算表.xlsx"

# 设备模式选项 - "simulated" 使用模拟设备，"serial" 使用实际的STM32串口通信。
DEVICE_MODE_SIMULATED = "simulated"
DEVICE_MODE_SERIAL = "serial"

# 频谱分析仪模式选项 - "simulated" 使用模拟频谱分析仪，"visa" 使用实际的pyvisa频谱分析仪访问。
SPECTRUM_MODE_SIMULATED = "simulated"
SPECTRUM_MODE_VISA = "visa"

# 真实频谱仪配置档位 - 保留研究院原有 TCPIP 方案，同时加入西安研究所验证过的 GPIB 方案。
SPECTRUM_ANALYZER_PROFILE_RESEARCH = "research"
SPECTRUM_ANALYZER_PROFILE_XIAN_GPIB = "xian_gpib"

# 信号源控制模式选项 - "manual" 使用手动控制，"auto" 使用自动控制。
SIGNAL_SOURCE_CONTROL_MANUAL = "manual"
SIGNAL_SOURCE_CONTROL_AUTO = "auto"


@dataclass(frozen=True)
class AppDefaults:
    """全局默认参数集中放在这里，便于联调时快速改运行模式和默认频点。

    注意：这是冻结 dataclass，运行中不要直接改 DEFAULTS；如果需要在 UI 中临时变更，
    应从控件读取当前值并传入对应配置对象。
    """

    # 调试无硬件时保持 simulated；实机下发给 STM32 时改成 serial。
    device_mode: str = DEVICE_MODE_SIMULATED
    # 调试无频谱仪时保持 simulated；接真实频谱仪时改成 visa。
    spectrum_analyzer_mode: str = SPECTRUM_MODE_SIMULATED
    # 真实频谱仪选择档位：research 使用研究院现有 TCPIP/VISA 方式，xian_gpib 使用西安所 GPIB 方式。
    spectrum_analyzer_profile: str = SPECTRUM_ANALYZER_PROFILE_RESEARCH
    # 研究院现有频谱仪的 pyvisa 资源地址，实机联调连接失败时优先检查这里。
    visa_address: str = "TCPIP::10.18.18.2::INSTR"
    # 西安研究所已验证的 FSQ40 GPIB 地址。
    xian_gpib_visa_address: str = "GPIB0::20::INSTR"
    # 真实频谱仪连接超时。
    spectrum_analyzer_timeout_ms: int = 5000
    # 信号源默认手动控制，避免无仪器或地址未配置时误下发 VISA/SCPI 命令。 TCPIP::0.0.0.0::INSTR
    signal_source_control_mode: str = SIGNAL_SOURCE_CONTROL_MANUAL
    lo_signal_source_visa_address: str = "TCPIP0::10.18.18.4::hislip0::INSTR"
    if_signal_source_visa_address: str = "TCPIP0::10.18.18.3::hislip0::INSTR"
    signal_source_timeout_ms: int = 5000
    signal_source_frequency_plan_path: Path = FREQUENCY_PLAN_PATH
    # UI0/模拟频谱仪使用的默认测试频点，UI1 也默认用它计算波束配相。
    frequency_ghz: float = 212.0
    # UI0 校准记录里的波束角默认值；UI1 的 θ0 默认值在 phase_config_window.py。
    beam_angle_deg: float = 30.0
    # UI0 扫描相位范围，使用 Decimal 生成点位以避免浮点步进丢点。
    phase_start_deg: float = 0.0
    phase_end_deg: float = 354.375
    phase_step_deg: float = 5.625
    # 当前硬件和 UI 都按四馈源阵列设计。
    feed_count: int = 4
    # amplitude 暂不写入 STM32 payload，但保留在 FeedState 中方便后续扩展。
    default_amplitude: float = 0.12
    # 每次相位下发后等待硬件稳定的默认时间。
    settle_time_ms: int = 500
    # UI0 每个相位点读取频谱仪的次数，最后取平均值。
    sample_count: int = 3
    # 串口默认值用于启动后还没有枚举到串口时兜底。
    serial_port: str = "COM1"
    serial_baudrate: int = 9600


DEFAULTS = AppDefaults()


def _normalize_mode(name: str, mode: str, allowed: tuple[str, ...]) -> str:
    """把运行模式字符串规范化，并在写错配置时尽早报错。"""
    normalized = mode.strip().lower()
    if normalized not in allowed:
        choices = ", ".join(allowed)
        raise ValueError(f"{name} must be one of: {choices}")
    return normalized


def create_device_controller(serial_port: str | None = None, mode: str | None = None):
    """按配置创建下位机控制器。

    调试定位：
    - UI 数据最终都会通过 DeviceController 发送。
    - 如果没有硬件，保持 simulated，可在界面里看到完整 HEX 但不会走串口。
    - 如果要实机发送，切到 serial 并检查 serial_port。
    """
    from .controllers import DeviceController
    from .transport import SerialTransport, SimulatedTransport

    selected = _normalize_mode(
        "device_mode",
        mode or DEFAULTS.device_mode,
        (DEVICE_MODE_SIMULATED, DEVICE_MODE_SERIAL),
    )
    if selected == DEVICE_MODE_SERIAL:
        return DeviceController(SerialTransport(serial_port or DEFAULTS.serial_port, DEFAULTS.serial_baudrate))

    return DeviceController(SimulatedTransport())


def create_spectrum_analyzer(mode: str | None = None):
    """按配置创建频谱仪读数对象。

    UI0 扫描功率时调用；模拟模式会生成可重复的相位-功率曲线，方便无仪器调试。
    """
    from .instruments import (
        SimulatedSpectrumAnalyzer,
        VisaSpectrumAnalyzer,
        XianGpibSpectrumAnalyzer,
    )

    selected = _normalize_mode(
        "spectrum_analyzer_mode",
        mode or DEFAULTS.spectrum_analyzer_mode,
        (SPECTRUM_MODE_SIMULATED, SPECTRUM_MODE_VISA),
    )
    if selected == SPECTRUM_MODE_VISA:
        profile = _normalize_mode(
            "spectrum_analyzer_profile",
            DEFAULTS.spectrum_analyzer_profile,
            (SPECTRUM_ANALYZER_PROFILE_RESEARCH, SPECTRUM_ANALYZER_PROFILE_XIAN_GPIB),
        )
        if profile == SPECTRUM_ANALYZER_PROFILE_XIAN_GPIB:
            return XianGpibSpectrumAnalyzer(
                DEFAULTS.xian_gpib_visa_address,
                DEFAULTS.spectrum_analyzer_timeout_ms,
            )
        return VisaSpectrumAnalyzer(DEFAULTS.visa_address, DEFAULTS.spectrum_analyzer_timeout_ms)

    return SimulatedSpectrumAnalyzer(DEFAULTS.visa_address)


def create_signal_source_controller(mode: str | None = None):
    """Create the dual signal-source controller when automatic control is enabled.

    When an address contains ``0.0.0.0`` the corresponding source is replaced by a
    simulated generator so that the other source can still be used with a real instrument.
    """
    from .instruments import SignalSourceController, SimulatedSignalGenerator, VisaSignalGenerator

    selected = _normalize_mode(
        "signal_source_control_mode",
        mode or DEFAULTS.signal_source_control_mode,
        (SIGNAL_SOURCE_CONTROL_MANUAL, SIGNAL_SOURCE_CONTROL_AUTO),
    )
    if selected == SIGNAL_SOURCE_CONTROL_MANUAL:
        return None

    def _make_source(name: str, address: str):
        if "0.0.0.0" in address:
            return SimulatedSignalGenerator(name=name, address=address)
        return VisaSignalGenerator(name, address, DEFAULTS.signal_source_timeout_ms)

    return SignalSourceController(
        lo_source=_make_source("LO", DEFAULTS.lo_signal_source_visa_address),
        if_source=_make_source("IF", DEFAULTS.if_signal_source_visa_address),
    )
