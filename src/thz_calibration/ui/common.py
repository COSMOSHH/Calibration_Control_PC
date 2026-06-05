from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox, QFileDialog, QLineEdit, QWidget


def set_locked(widget: QWidget, locked: bool) -> None:
    """统一设置控件锁定状态和 locked 样式属性。

    只调用 setEnabled 会改变交互，但 QSS 里需要 locked 属性来显示灰底样式；
    unpolish/polish 用于强制 Qt 立即重新计算样式。
    """
    widget.setEnabled(not locked)
    widget.setProperty("locked", "true" if locked else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def lock_widgets(widgets: list[QWidget], locked: bool) -> None:
    """批量锁定/解锁一组控件，常用于“确认后禁止改参数”。"""
    for widget in widgets:
        set_locked(widget, locked)


def make_spin(
    value: float,
    minimum: float = -9999.0,
    maximum: float = 9999.0,
    decimals: int = 3,
    width: int = 78,
) -> QDoubleSpinBox:
    """创建项目里统一外观的数值输入框。

    默认隐藏上下箭头，界面更接近原始设计图；需要调试范围限制时优先看
    调用处传入的 minimum/maximum。
    """
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(1.0)
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    spin.setValue(value)
    spin.setFixedWidth(width)
    return spin


def make_line(value: str = "", width: int = 150) -> QLineEdit:
    """创建固定宽度文本输入框。"""
    edit = QLineEdit(value)
    edit.setFixedWidth(width)
    return edit


def browse_directory(parent: QWidget, current: str) -> str:
    """打开目录选择对话框；用户取消时保留当前路径。"""
    path = QFileDialog.getExistingDirectory(parent, "选择数据保存目录", current)
    return str(Path(path)) if path else current


def available_serial_ports(default_port: str) -> list[str]:
    """枚举当前系统可用串口。

    pyserial 未安装或系统没有枚举到串口时，返回 default_port 作为兜底，
    让 UI 仍然可以显示并手工输入/选择默认 COM。
    """
    try:
        import serial.tools.list_ports
    except ImportError:
        return [default_port]

    ports = [port.device for port in serial.tools.list_ports.comports()]
    if default_port and default_port not in ports:
        ports.insert(0, default_port)
    return ports or [default_port]
