from pathlib import Path

from thz_calibration.config import load_app_defaults


def test_external_config_overrides_runtime_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[device]
mode = serial
serial_port = COM7
serial_baudrate = 115200

[spectrum_analyzer]
mode = visa
profile = research
visa_backend = py
visa_address = TCPIP0::127.0.0.1::5025::SOCKET

[calibration]
frequency_ghz = 224
sample_count = 5
""".strip(),
        encoding="utf-8",
    )

    defaults = load_app_defaults(config_path)

    assert defaults.device_mode == "serial"
    assert defaults.serial_port == "COM7"
    assert defaults.serial_baudrate == 115200
    assert defaults.spectrum_analyzer_mode == "visa"
    assert defaults.visa_backend == "py"
    assert defaults.visa_address == "TCPIP0::127.0.0.1::5025::SOCKET"
    assert defaults.frequency_ghz == 224
    assert defaults.sample_count == 5


def test_invalid_choice_falls_back_to_builtin_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text("[device]\nmode = invalid\n", encoding="utf-8")

    defaults = load_app_defaults(config_path)

    assert defaults.device_mode == "simulated"
