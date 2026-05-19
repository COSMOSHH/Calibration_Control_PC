from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs"
TEMPLATE_DIR = DOCS_DIR / "馈源间相位校准数据保存格式"
OUTPUT_DIR = ROOT_DIR / "output"

# 设备模式选项 - "simulated" 使用模拟设备，"serial" 使用实际的STM32串口通信。
DEVICE_MODE_SIMULATED = "simulated"
DEVICE_MODE_SERIAL = "serial"

# 频谱分析仪模式选项 - "simulated" 使用模拟频谱分析仪，"visa" 使用实际的pyvisa频谱分析仪访问。
SPECTRUM_MODE_SIMULATED = "simulated"
SPECTRUM_MODE_VISA = "visa"


@dataclass(frozen=True)
class AppDefaults:
    # Switch to "serial" for real STM32 serial transport.
    device_mode: str = DEVICE_MODE_SIMULATED
    # Switch to "visa" for real pyvisa spectrum analyzer access.
    spectrum_analyzer_mode: str = SPECTRUM_MODE_SIMULATED
    visa_address: str = "TCPIP::10.18.18.2::INSTR"
    frequency_ghz: float = 212.0
    beam_angle_deg: float = 30.0
    phase_start_deg: float = 0.0
    phase_end_deg: float = 354.375
    phase_step_deg: float = 5.625
    feed_count: int = 4
    default_amplitude: float = 0.12
    settle_time_ms: int = 500
    sample_count: int = 3
    serial_port: str = "COM1"
    serial_baudrate: int = 9600


DEFAULTS = AppDefaults()


def _normalize_mode(name: str, mode: str, allowed: tuple[str, ...]) -> str:
    normalized = mode.strip().lower()
    if normalized not in allowed:
        choices = ", ".join(allowed)
        raise ValueError(f"{name} must be one of: {choices}")
    return normalized


def create_device_controller(serial_port: str | None = None, mode: str | None = None):
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
    from .instruments import SimulatedSpectrumAnalyzer, VisaSpectrumAnalyzer

    selected = _normalize_mode(
        "spectrum_analyzer_mode",
        mode or DEFAULTS.spectrum_analyzer_mode,
        (SPECTRUM_MODE_SIMULATED, SPECTRUM_MODE_VISA),
    )
    if selected == SPECTRUM_MODE_VISA:
        return VisaSpectrumAnalyzer(DEFAULTS.visa_address)

    return SimulatedSpectrumAnalyzer(DEFAULTS.visa_address)
