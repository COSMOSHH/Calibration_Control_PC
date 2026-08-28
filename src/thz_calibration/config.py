from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path


# 源码运行时以仓库根目录为应用目录；冻结后以 exe 所在目录为应用目录。
# PyInstaller 会把只读资源放在 sys._MEIPASS，而 config.ini/output 必须留在 exe 外部。
SOURCE_ROOT_DIR = Path(__file__).resolve().parents[2]
IS_FROZEN = bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else SOURCE_ROOT_DIR
RESOURCE_DIR = Path(sys._MEIPASS).resolve() if IS_FROZEN else SOURCE_ROOT_DIR
ROOT_DIR = APP_DIR
DOCS_DIR = RESOURCE_DIR / "docs"
TEMPLATE_DIR = DOCS_DIR / "馈源间相位校准数据保存格式"
FREQUENCY_PLAN_PATH = DOCS_DIR / "说明文档" / "中频和本振频率核算表.xlsx"
CONFIG_PATH = Path(os.environ.get("THZ_CALIBRATION_CONFIG", APP_DIR / "config.ini")).resolve()
CONFIG_WARNINGS: list[str] = []

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

# 转台控制模式选项 - "simulated" 只走软件模拟，"serial" 使用 GCD-030401M Modbus RTU。
TURNTABLE_MODE_SIMULATED = "simulated"
TURNTABLE_MODE_SERIAL = "serial"


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
    # auto 使用系统默认 VISA；ivi 强制厂商 VISA Runtime；py 强制随软件打包的 pyvisa-py。
    visa_backend: str = "auto"
    # 研究院现有频谱仪的 pyvisa 资源地址，实机联调连接失败时优先检查这里。
    visa_address: str = "TCPIP0::10.18.18.4::5025::SOCKET"
    # 西安研究所已验证的 FSQ40 GPIB 地址。
    xian_gpib_visa_address: str = "GPIB0::20::INSTR"
    # 真实频谱仪连接超时。
    spectrum_analyzer_timeout_ms: int = 5000
    # 真实频谱仪读数前自动设置的扫频宽度，默认 2 MHz。
    spectrum_analyzer_span_ghz: float = 0.002
    # 频谱仪预测试设置：201 个点从起始频率扫到终止频率。
    spectrum_analyzer_scan_points: int = 201
    # 当前使用仪器默认扫频时间；如以后需要手动设置，可恢复下面的点间隔配置。
    # spectrum_analyzer_scan_point_interval_ms: float = 1.0
    # 频谱仪分辨率带宽 RBW（Resolution Bandwidth），默认 1 kHz。
    spectrum_analyzer_rbw_hz: float = 1000.0
    # 频谱仪视频带宽 VBW（Video Bandwidth），默认 1 kHz。
    spectrum_analyzer_vbw_hz: float = 1000.0
    # 频谱仪实际观察频率换算系数：无扩频模块调试时按“当前校准频率 / 10”观察；正式接扩频模块时改为 1.0。
    spectrum_analyzer_frequency_divisor: float = 10.0
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
    # UI0 配置给频谱仪内置平均功能的平均次数；每个相位点只读取一次硬件平均后的 marker 功率。
    sample_count: int = 3
    # 串口默认值用于启动后还没有枚举到串口时兜底。
    serial_port: str = "COM1"
    serial_baudrate: int = 9600
    # UI0 波束指向角对应真实转台角度；默认保持 simulated，点击 UI0“转台连接”后强制使用 serial。
    turntable_mode: str = TURNTABLE_MODE_SIMULATED
    turntable_port: str = "COM1"
    turntable_baudrate: int = 38400
    turntable_slave_id: int = 1
    turntable_pulses_per_degree: float = 2000.0
    turntable_move_timeout_s: float = 30.0
    turntable_poll_interval_s: float = 0.05
    turntable_settle_time_s: float = 0.12


def _read_external_config(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    if not path.exists():
        return parser
    try:
        parser.read_string(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, configparser.Error) as exc:
        CONFIG_WARNINGS.append(f"配置文件读取失败，将使用内置默认值：{path}\n{exc}")
    return parser


def _config_value(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    fallback,
    converter,
):
    if not parser.has_option(section, option):
        return fallback
    raw = parser.get(section, option)
    try:
        return converter(raw.strip())
    except (TypeError, ValueError) as exc:
        CONFIG_WARNINGS.append(
            f"config.ini 参数 [{section}] {option}={raw!r} 无效，已使用默认值 {fallback!r}：{exc}"
        )
        return fallback


def _string_value(parser: configparser.ConfigParser, section: str, option: str, fallback: str) -> str:
    return _config_value(parser, section, option, fallback, str)


def _choice_value(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    fallback: str,
    allowed: tuple[str, ...],
) -> str:
    def convert(raw: str) -> str:
        value = raw.lower()
        if value not in allowed:
            raise ValueError(f"可选值：{', '.join(allowed)}")
        return value

    return _config_value(parser, section, option, fallback, convert)


def load_app_defaults(
    config_path: Path = CONFIG_PATH,
    parser: configparser.ConfigParser | None = None,
) -> AppDefaults:
    """Load editable runtime settings while retaining safe built-in fallbacks."""
    parser = parser if parser is not None else _read_external_config(Path(config_path))
    defaults = AppDefaults()
    return replace(
        defaults,
        device_mode=_choice_value(
            parser,
            "device",
            "mode",
            defaults.device_mode,
            (DEVICE_MODE_SIMULATED, DEVICE_MODE_SERIAL),
        ),
        serial_port=_string_value(parser, "device", "serial_port", defaults.serial_port),
        serial_baudrate=_config_value(
            parser, "device", "serial_baudrate", defaults.serial_baudrate, int
        ),
        spectrum_analyzer_mode=_choice_value(
            parser,
            "spectrum_analyzer",
            "mode",
            defaults.spectrum_analyzer_mode,
            (SPECTRUM_MODE_SIMULATED, SPECTRUM_MODE_VISA),
        ),
        spectrum_analyzer_profile=_choice_value(
            parser,
            "spectrum_analyzer",
            "profile",
            defaults.spectrum_analyzer_profile,
            (SPECTRUM_ANALYZER_PROFILE_RESEARCH, SPECTRUM_ANALYZER_PROFILE_XIAN_GPIB),
        ),
        visa_backend=_choice_value(
            parser, "spectrum_analyzer", "visa_backend", defaults.visa_backend, ("auto", "ivi", "py")
        ),
        visa_address=_string_value(
            parser, "spectrum_analyzer", "visa_address", defaults.visa_address
        ),
        xian_gpib_visa_address=_string_value(
            parser, "spectrum_analyzer", "xian_gpib_address", defaults.xian_gpib_visa_address
        ),
        spectrum_analyzer_timeout_ms=_config_value(
            parser,
            "spectrum_analyzer",
            "timeout_ms",
            defaults.spectrum_analyzer_timeout_ms,
            int,
        ),
        spectrum_analyzer_span_ghz=_config_value(
            parser,
            "spectrum_analyzer",
            "span_ghz",
            defaults.spectrum_analyzer_span_ghz,
            float,
        ),
        spectrum_analyzer_scan_points=_config_value(
            parser,
            "spectrum_analyzer",
            "scan_points",
            defaults.spectrum_analyzer_scan_points,
            int,
        ),
        spectrum_analyzer_rbw_hz=_config_value(
            parser, "spectrum_analyzer", "rbw_hz", defaults.spectrum_analyzer_rbw_hz, float
        ),
        spectrum_analyzer_vbw_hz=_config_value(
            parser, "spectrum_analyzer", "vbw_hz", defaults.spectrum_analyzer_vbw_hz, float
        ),
        spectrum_analyzer_frequency_divisor=_config_value(
            parser,
            "spectrum_analyzer",
            "frequency_divisor",
            defaults.spectrum_analyzer_frequency_divisor,
            float,
        ),
        signal_source_control_mode=_choice_value(
            parser,
            "signal_source",
            "mode",
            defaults.signal_source_control_mode,
            (SIGNAL_SOURCE_CONTROL_MANUAL, SIGNAL_SOURCE_CONTROL_AUTO),
        ),
        lo_signal_source_visa_address=_string_value(
            parser, "signal_source", "lo_visa_address", defaults.lo_signal_source_visa_address
        ),
        if_signal_source_visa_address=_string_value(
            parser, "signal_source", "if_visa_address", defaults.if_signal_source_visa_address
        ),
        signal_source_timeout_ms=_config_value(
            parser, "signal_source", "timeout_ms", defaults.signal_source_timeout_ms, int
        ),
        frequency_ghz=_config_value(
            parser, "calibration", "frequency_ghz", defaults.frequency_ghz, float
        ),
        beam_angle_deg=_config_value(
            parser, "calibration", "beam_angle_deg", defaults.beam_angle_deg, float
        ),
        phase_start_deg=_config_value(
            parser, "calibration", "phase_start_deg", defaults.phase_start_deg, float
        ),
        phase_end_deg=_config_value(
            parser, "calibration", "phase_end_deg", defaults.phase_end_deg, float
        ),
        phase_step_deg=_config_value(
            parser, "calibration", "phase_step_deg", defaults.phase_step_deg, float
        ),
        default_amplitude=_config_value(
            parser, "calibration", "default_amplitude", defaults.default_amplitude, float
        ),
        settle_time_ms=_config_value(
            parser, "calibration", "settle_time_ms", defaults.settle_time_ms, int
        ),
        sample_count=_config_value(
            parser, "calibration", "sample_count", defaults.sample_count, int
        ),
        turntable_mode=_choice_value(
            parser,
            "turntable",
            "mode",
            defaults.turntable_mode,
            (TURNTABLE_MODE_SIMULATED, TURNTABLE_MODE_SERIAL),
        ),
        turntable_port=_string_value(parser, "turntable", "serial_port", defaults.turntable_port),
        turntable_baudrate=_config_value(
            parser, "turntable", "baudrate", defaults.turntable_baudrate, int
        ),
        turntable_slave_id=_config_value(
            parser, "turntable", "slave_id", defaults.turntable_slave_id, int
        ),
        turntable_pulses_per_degree=_config_value(
            parser,
            "turntable",
            "pulses_per_degree",
            defaults.turntable_pulses_per_degree,
            float,
        ),
        turntable_move_timeout_s=_config_value(
            parser, "turntable", "move_timeout_s", defaults.turntable_move_timeout_s, float
        ),
        turntable_poll_interval_s=_config_value(
            parser, "turntable", "poll_interval_s", defaults.turntable_poll_interval_s, float
        ),
        turntable_settle_time_s=_config_value(
            parser, "turntable", "settle_time_s", defaults.turntable_settle_time_s, float
        ),
    )


def _external_path(parser: configparser.ConfigParser, section: str, option: str, fallback: str) -> Path:
    raw = _string_value(parser, section, option, fallback)
    path = Path(os.path.expandvars(raw)).expanduser()
    return path.resolve() if path.is_absolute() else (CONFIG_PATH.parent / path).resolve()


_EXTERNAL_CONFIG = _read_external_config(CONFIG_PATH)
DEFAULTS = load_app_defaults(CONFIG_PATH, _EXTERNAL_CONFIG)
OUTPUT_DIR = _external_path(_EXTERNAL_CONFIG, "paths", "output_dir", "output")


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
                address=DEFAULTS.xian_gpib_visa_address,
                visa_backend=DEFAULTS.visa_backend,
                timeout_ms=DEFAULTS.spectrum_analyzer_timeout_ms,
                sweep_span_ghz=DEFAULTS.spectrum_analyzer_span_ghz,
                frequency_divisor=DEFAULTS.spectrum_analyzer_frequency_divisor,
                sweep_points=DEFAULTS.spectrum_analyzer_scan_points,
                rbw_hz=DEFAULTS.spectrum_analyzer_rbw_hz,
                vbw_hz=DEFAULTS.spectrum_analyzer_vbw_hz,
            )
        return VisaSpectrumAnalyzer(
            address=DEFAULTS.visa_address,
            visa_backend=DEFAULTS.visa_backend,
            timeout_ms=DEFAULTS.spectrum_analyzer_timeout_ms,
            sweep_span_ghz=DEFAULTS.spectrum_analyzer_span_ghz,
            frequency_divisor=DEFAULTS.spectrum_analyzer_frequency_divisor,
            sweep_points=DEFAULTS.spectrum_analyzer_scan_points,
            rbw_hz=DEFAULTS.spectrum_analyzer_rbw_hz,
            vbw_hz=DEFAULTS.spectrum_analyzer_vbw_hz,
        )

    return SimulatedSpectrumAnalyzer(
        address=DEFAULTS.visa_address,
        sweep_span_ghz=DEFAULTS.spectrum_analyzer_span_ghz,
        frequency_divisor=DEFAULTS.spectrum_analyzer_frequency_divisor,
        sweep_points=DEFAULTS.spectrum_analyzer_scan_points,
        rbw_hz=DEFAULTS.spectrum_analyzer_rbw_hz,
        vbw_hz=DEFAULTS.spectrum_analyzer_vbw_hz,
    )


def create_turntable_controller(serial_port: str | None = None, mode: str | None = None):
    """按配置创建 UI0 波束指向角使用的转台控制器。

    UI0 只需要单个目标角度，不创建起始/终止/步长扫描；控制器会把目标角
    作为 HOME/设零后的绝对角度交给 GCD-030401M 驱动写 Modbus RTU 寄存器。
    """
    from .controllers import TurntableController
    from .instruments import GcdTurntableDriver, SimulatedTurntableDriver

    selected = _normalize_mode(
        "turntable_mode",
        mode or DEFAULTS.turntable_mode,
        (TURNTABLE_MODE_SIMULATED, TURNTABLE_MODE_SERIAL),
    )
    if selected == TURNTABLE_MODE_SERIAL:
        driver = GcdTurntableDriver(
            port=serial_port or DEFAULTS.turntable_port,
            baudrate=DEFAULTS.turntable_baudrate,
            slave_id=DEFAULTS.turntable_slave_id,
            pulses_per_degree=DEFAULTS.turntable_pulses_per_degree,
            move_timeout_s=DEFAULTS.turntable_move_timeout_s,
            poll_interval_s=DEFAULTS.turntable_poll_interval_s,
        )
    else:
        driver = SimulatedTurntableDriver()

    return TurntableController(driver, settle_time_s=DEFAULTS.turntable_settle_time_s)


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
        return VisaSignalGenerator(
            name,
            address,
            DEFAULTS.signal_source_timeout_ms,
            visa_backend=DEFAULTS.visa_backend,
        )

    return SignalSourceController(
        lo_source=_make_source("LO", DEFAULTS.lo_signal_source_visa_address),
        if_source=_make_source("IF", DEFAULTS.if_signal_source_visa_address),
    )
