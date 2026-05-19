from __future__ import annotations

import sys


def _arg_value(flag: str, default: str | None = None) -> str | None:
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(sys.argv):
        return default
    return sys.argv[index + 1]


def main() -> None:
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from .ui import CalibrationTestWindow, PhaseConfigWindow

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 9))
    app.setStyle("Fusion")

    args = set(sys.argv[1:])
    serial_port = _arg_value("--serial-port")

    if "--config" in args:
        window = PhaseConfigWindow(serial_port=serial_port)
    else:
        window = CalibrationTestWindow(serial_port=serial_port)

    window.show()

    sys.exit(app.exec())
