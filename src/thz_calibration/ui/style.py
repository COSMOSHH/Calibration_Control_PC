from __future__ import annotations

# 全局 QSS 样式集中放在这里，两个主窗口共用。
# 调试控件禁用样式时注意 common.set_locked() 会设置 locked 属性，
# 下面的 QLineEdit[locked="true"] / QDoubleSpinBox[locked="true"] 依赖它生效。
APP_STYLESHEET = """
QMainWindow {
    background: #f6f6f6;
}
QWidget {
    font-family: "Microsoft YaHei", "SimSun";
    font-size: 13px;
    color: #111111;
}
QFrame#Shell {
    background: #f7f7f7;
    border: 1px solid #8c8c8c;
    border-radius: 8px;
}
QGroupBox {
    border: 1px solid #b7b7b7;
    margin-top: 16px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #555555;
    font-family: "KaiTi", "SimSun";
    font-size: 14px;
}
QPushButton {
    min-height: 22px;
    padding: 1px 13px;
    color: #00316a;
    border: 1px solid #9f9f9f;
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:0.45 #eeeeee, stop:0.55 #d6d6d6, stop:1 #ffffff);
    font-weight: 600;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #cfcfcf, stop:1 #ffffff);
}
QPushButton:checked {
    color: #001f48;
    border: 1px solid #6f6f6f;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #cfcfcf, stop:0.45 #eeeeee, stop:1 #ffffff);
}
QLineEdit, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #6f6f6f;
    min-height: 22px;
    padding: 0 6px;
    selection-background-color: #bfd7ff;
}
QLineEdit[locked="true"], QDoubleSpinBox[locked="true"] {
    background: #f5f5f5;
    color: #555555;
}
QCheckBox {
    spacing: 7px;
}
QTextEdit {
    background: #ffffff;
    border: 0;
    font-family: "SimSun";
    font-size: 14px;
}
QLabel#WindowTitle {
    color: #004093;
    font-size: 16px;
    font-weight: 700;
}
QLabel#SoftTitle {
    color: #004093;
    font-size: 24px;
    font-weight: 800;
}
QLabel#SectionNote {
    color: #555555;
    font-family: "KaiTi", "SimSun";
    font-size: 14px;
}
"""
