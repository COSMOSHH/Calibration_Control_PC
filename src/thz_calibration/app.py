from __future__ import annotations

import sys


def _arg_value(flag: str, default: str | None = None) -> str | None:
    """读取形如 --serial-port COM3 的命令行参数值。

    这里不用 argparse，是为了让三个轻量入口脚本保持简单；如果后续命令行
    参数明显增多，可以把这段替换成 argparse.ArgumentParser。
    """
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(sys.argv):
        return default
    return sys.argv[index + 1]


def main() -> None:
    """创建 QApplication，并按命令行参数打开对应窗口。

    调试入口：
    - 默认或 --calibration：打开 UI0 校准数据测试窗口。
    - --config：打开 UI1 相位配置窗口。
    - --serial-port COMx：启动时指定默认串口。
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from .ui import CalibrationTestWindow, PhaseConfigWindow

    # QApplication 必须在所有 QWidget 创建前存在；字体和 Fusion 样式在这里统一设置。
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 9))
    app.setStyle("Fusion")

    args = set(sys.argv[1:])
    serial_port = _arg_value("--serial-port")

    # 两套 UI 共享同一个 app 入口，避免启动脚本里重复创建 QApplication。
    if "--config" in args:
        window = PhaseConfigWindow(serial_port=serial_port)
    else:
        window = CalibrationTestWindow(serial_port=serial_port)

    window.show()

    sys.exit(app.exec())
