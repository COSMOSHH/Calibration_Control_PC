from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox, QFileDialog, QLineEdit, QWidget


def set_locked(widget: QWidget, locked: bool) -> None:
    widget.setEnabled(not locked)
    widget.setProperty("locked", "true" if locked else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def lock_widgets(widgets: list[QWidget], locked: bool) -> None:
    for widget in widgets:
        set_locked(widget, locked)


def make_spin(
    value: float,
    minimum: float = -9999.0,
    maximum: float = 9999.0,
    decimals: int = 3,
    width: int = 78,
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(1.0)
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    spin.setValue(value)
    spin.setFixedWidth(width)
    return spin


def make_line(value: str = "", width: int = 150) -> QLineEdit:
    edit = QLineEdit(value)
    edit.setFixedWidth(width)
    return edit


def browse_directory(parent: QWidget, current: str) -> str:
    path = QFileDialog.getExistingDirectory(parent, "选择数据保存目录", current)
    return str(Path(path)) if path else current


def available_serial_ports(default_port: str) -> list[str]:
    try:
        import serial.tools.list_ports
    except ImportError:
        return [default_port]

    ports = [port.device for port in serial.tools.list_ports.comports()]
    if default_port and default_port not in ports:
        ports.insert(0, default_port)
    return ports or [default_port]
