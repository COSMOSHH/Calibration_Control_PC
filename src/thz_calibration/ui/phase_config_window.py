from __future__ import annotations

from math import sin, pi

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import DEFAULTS, DEVICE_MODE_SERIAL, create_device_controller
from ..data import ExcelExporter
from ..models import FeedState
from .common import available_serial_ports, lock_widgets, make_spin, set_locked
from .style import APP_STYLESHEET

# 下面这些常量用于波束指向配相计算和默认输入值。
LIGHT_SPEED_MPS = 3.0e8 # 光速 m/s
FEED_SPACING_M = 15.52e-3 # 四馈源阵列设计中相邻馈源间距，单位 m；这个值会影响波束配相计算结果。
GHZ_TO_HZ = 1.0e9 # 输出频率输入单位是 GHz，计算时需要换算成 Hz, 用于频率单位转换。
# UI1 默认输入值：θ0 和四个馈源相位都从 0 deg 开始。
DEFAULT_BEAM_THETA_DEG = 0.0 # 波束指向角 θ0 的默认值；UI0 校准记录里的波束角默认值在 config.py。
DEFAULT_FEED_PHASE_DEG = 0.0 


class PhaseConfigWindow(QMainWindow):
    """UI1：馈源阵输出相位配置窗口。

    主要调试路线：
    - 基础设置：输出频率、本振/中频功率、串口连接。
    - 相位配置：手动输入四馈源相位，或勾选“通过波束指向配相”自动计算。
    - 自动校准：读取 UI0 生成的最佳相位表，把期望相位叠加校准偏移。
    - 数据发送：phase_queue -> DeviceController -> 协议 HEX -> 串口/模拟传输。
    """

    def __init__(self, serial_port: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("分布式有源驱动馈源阵输出相位配置软件")
        self.setFixedSize(1280, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self.serial_port_default = serial_port or DEFAULTS.serial_port
        self.device = create_device_controller(self.serial_port_default)
        self.device.connect()
        self.exporter = ExcelExporter()
        # phase_queue 是最终待发送队列；相位确认/初始同步/自动校准都会写入它。
        self.phase_queue: list[FeedState] = []
        # 下面这些布尔状态用于避免重复确认、重复自动校准，以及驱动按钮 checked 状态。
        self.basic_confirmed = False
        self.phase_confirmed = False
        self.auto_calibrated = False
        self.lo_enabled = False
        self.if_enabled = False

        self._build_ui()
        self._initialize_button_states()

    def _build_ui(self) -> None:
        """组装 UI1 的三块区域：基础设置、相位配置、信息反馈窗。"""
        shell = QFrame()
        shell.setObjectName("Shell")
        self.setCentralWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(12, 4, 12, 10)
        root.setSpacing(8)

        title = QLabel("分布式有源驱动馈源阵输出相位配置软件")
        title.setObjectName("SoftTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        root.addWidget(self._build_basic_group())
        root.addWidget(self._build_phase_group(), stretch=1)
        root.addWidget(self._build_feedback_group(), stretch=1)

    def _build_basic_group(self) -> QGroupBox:
        """构建基础设置区。

        输出频率会参与波束指向配相计算；本振/中频按钮目前只维护 UI 状态和反馈，
        尚未下发独立硬件命令。
        """
        group = QGroupBox("基础设置")
        group.setFixedHeight(205)
        layout = QGridLayout(group)
        layout.setContentsMargins(34, 26, 34, 22)
        layout.setHorizontalSpacing(22)
        layout.setVerticalSpacing(16)

        self.basic_reset_btn = QPushButton("重 设")
        self.basic_reset_btn.setFixedWidth(92)
        self.basic_reset_btn.clicked.connect(self._reset_basic)
        self.basic_confirm_btn = QPushButton("确 认")
        self.basic_confirm_btn.setFixedWidth(92)
        self.basic_confirm_btn.clicked.connect(self._confirm_basic)
        self.lo_on_btn = QPushButton("本振开启")
        self.lo_on_btn.setFixedWidth(96)
        self.lo_off_btn = QPushButton("本振关闭")
        self.lo_off_btn.setFixedWidth(96)
        self.if_on_btn = QPushButton("中频开启")
        self.if_on_btn.setFixedWidth(96)
        self.if_off_btn = QPushButton("中频关闭")
        self.if_off_btn.setFixedWidth(96)
        for button in (
            self.basic_reset_btn,
            self.basic_confirm_btn,
            self.lo_on_btn,
            self.lo_off_btn,
            self.if_on_btn,
            self.if_off_btn,
        ):
            button.setCheckable(True)

        self.serial_combo = QComboBox()
        self.serial_combo.setFixedWidth(118)
        self.refresh_serial_btn = QPushButton("刷新")
        self.refresh_serial_btn.setFixedWidth(82)
        self.refresh_serial_btn.clicked.connect(self._refresh_serial_ports)
        self.serial_btn = QPushButton("串口连接")
        self.serial_btn.setFixedWidth(118)
        self.serial_btn.clicked.connect(self._connect_serial)
        self._refresh_serial_ports()

        self.output_freq_spin = make_spin(DEFAULTS.frequency_ghz, 1, 1000, 3, 96)
        self.basic_lo_power_spin = make_spin(-20.0, -100, 30, 3, 96)
        self.basic_if_power_spin = make_spin(-20.0, -100, 30, 3, 96)

        serial_panel = QWidget()
        serial_layout = QGridLayout(serial_panel)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.setHorizontalSpacing(10)
        serial_layout.setVerticalSpacing(12)
        serial_layout.addWidget(QLabel("串口"), 0, 0, Qt.AlignRight)
        serial_layout.addWidget(self.serial_combo, 0, 1)
        serial_layout.addWidget(self.refresh_serial_btn, 0, 2)
        serial_layout.addWidget(self.serial_btn, 1, 1, 1, 2, Qt.AlignLeft)

        output_column = self._basic_param_column("输出频率（GHz）", self.output_freq_spin, self.basic_confirm_btn)
        lo_column = self._basic_param_column("本振源功率（dBm）", self.basic_lo_power_spin, self.lo_on_btn, self.lo_off_btn)
        if_column = self._basic_param_column("中频源功率（dBm）", self.basic_if_power_spin, self.if_on_btn, self.if_off_btn)
        reset_column = self._basic_button_column(self.basic_reset_btn)

        layout.addWidget(reset_column, 0, 0, Qt.AlignHCenter)
        layout.addWidget(output_column, 1, 0, Qt.AlignHCenter)
        layout.addWidget(lo_column, 1, 1, Qt.AlignHCenter)
        layout.addWidget(if_column, 1, 2, Qt.AlignHCenter)
        layout.addWidget(serial_panel, 0, 3, 2, 1, Qt.AlignTop | Qt.AlignRight)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)

        self.lo_on_btn.clicked.connect(lambda: self._set_source_state("lo", True))
        self.lo_off_btn.clicked.connect(lambda: self._set_source_state("lo", False))
        self.if_on_btn.clicked.connect(lambda: self._set_source_state("if", True))
        self.if_off_btn.clicked.connect(lambda: self._set_source_state("if", False))

        self.basic_inputs = [
            self.output_freq_spin,
            self.basic_lo_power_spin,
            self.basic_if_power_spin,
        ]
        return group

    def _basic_param_column(
        self,
        label_text: str,
        editor: QWidget,
        *buttons: QPushButton,
        label_alignment: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter,
    ) -> QWidget:
        """创建基础设置区的一列参数，让标签、输入框和按钮共享同一左边界。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(36)
        layout.addWidget(
            self._field_pair(
                label_text,
                editor,
                250,
                label_width=118,
                label_alignment=label_alignment,
            )
        )
        layout.addWidget(self._button_row(*buttons), alignment=Qt.AlignLeft)
        widget.setFixedWidth(250)
        return widget

    def _basic_button_column(self, button: QPushButton) -> QWidget:
        """创建和基础参数列同宽的单按钮容器，用来对齐重设/确认。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(button)
        layout.addStretch(1)
        widget.setFixedWidth(250)
        return widget

    def _button_row(self, *buttons: QPushButton) -> QWidget:
        """创建一行并排按钮，供基础设置区复用。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for button in buttons:
            layout.addWidget(button)
        layout.addStretch(1)
        return widget

    def _basic_column(
        self,
        label_text: str,
        editor: QWidget,
        left_button: QPushButton | None,
        right_button: QPushButton | None,
        width: int,
        label_width: int = 146,
    ) -> QWidget:
        """基础设置区里“功率输入 + 开关按钮”的复用布局。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._field_pair(label_text, editor, width, label_width=label_width))
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(12)
        if left_button is not None:
            button_row.addWidget(left_button)
        if right_button is not None:
            button_row.addWidget(right_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        widget.setFixedWidth(width)
        return widget

    def _build_phase_group(self) -> QGroupBox:
        """构建相位配置区。

        手动模式下四个馈源相位可编辑，θ0 禁用；波束配相模式下四个相位由公式
        自动计算，θ0 启用，φ0 只作为可编辑占位输入，不参与计算。
        """
        group = QGroupBox("相位/波束设置")
        group.setFixedHeight(338)
        layout = QGridLayout(group)
        layout.setContentsMargins(34, 28, 34, 24)
        layout.setHorizontalSpacing(22)
        layout.setVerticalSpacing(16)

        self.initial_sync_btn = QPushButton("初始同步")
        self.phase_reset_btn = QPushButton("相位重设")
        self.beam_checkbox = QCheckBox("通过波束指向配相")
        self.phase_confirm_btn = QPushButton("相位确认")
        self.auto_cal_btn = QPushButton("自动校准")
        self.data_send_btn = QPushButton("数据发送")
        for button in (
            self.initial_sync_btn,
            self.phase_reset_btn,
            self.phase_confirm_btn,
            self.auto_cal_btn,
            self.data_send_btn,
        ):
            button.setFixedWidth(264)
        self.phase_reset_btn.setCheckable(True)
        self.phase_confirm_btn.setCheckable(True)

        self.initial_sync_btn.clicked.connect(self._initial_sync)
        self.phase_reset_btn.clicked.connect(self._reset_phase_inputs)
        self.beam_checkbox.toggled.connect(self._on_beam_checkbox_toggled)
        self.phase_confirm_btn.clicked.connect(self._confirm_phase)
        self.auto_cal_btn.clicked.connect(self._auto_calibrate)
        self.data_send_btn.clicked.connect(self._send_data)

        layout.addWidget(self.initial_sync_btn, 0, 0, Qt.AlignLeft)
        layout.addWidget(self.phase_reset_btn, 0, 1, Qt.AlignLeft)
        layout.addWidget(self.beam_checkbox, 0, 2, 1, 2, Qt.AlignLeft | Qt.AlignVCenter)

        self.feed_phase_spins = {}
        for index, feed_id in enumerate((1, 2, 3, 4)):
            # feed_phase_spins 是 UI1 手动/自动配相共用的相位输入框集合。
            feed_box = QWidget()
            feed_layout = QVBoxLayout(feed_box)
            feed_layout.setContentsMargins(0, 0, 0, 0)
            feed_layout.setSpacing(14)
            feed_label = QLabel(f"馈源{feed_id}")
            feed_label.setAlignment(Qt.AlignCenter)
            phase_spin = make_spin(DEFAULT_FEED_PHASE_DEG, 0, 360, 3, 96)
            self.feed_phase_spins[feed_id] = phase_spin
            feed_layout.addWidget(feed_label)
            feed_layout.addWidget(self._field_pair("相位配置（deg）", phase_spin, 250, label_width=118))
            layout.addWidget(feed_box, 1, index, Qt.AlignHCenter)
            layout.setColumnStretch(index, 1)

        self.theta_spin = make_spin(DEFAULT_BEAM_THETA_DEG, -9999, 9999, 3, 96)
        self.phi_spin = make_spin(0.0, -180, 180, 3, 96)
        # θ0 或频率变化时，若处于波束配相模式，立即刷新四个相位显示值。
        self.theta_spin.valueChanged.connect(self._update_beam_phase_values)
        self.output_freq_spin.valueChanged.connect(self._update_beam_phase_values)
        theta_pair = self._field_pair(
            "波束指向角度 θ₀（deg）",
            self.theta_spin,
            270,
            label_width=164,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            label_indent=0,
        )
        phi_pair = self._field_pair(
            "波束指向角度 φ₀（deg）",
            self.phi_spin,
            270,
            label_width=164,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            label_indent=0,
        )
        layout.addWidget(theta_pair, 2, 0, Qt.AlignHCenter)
        layout.addWidget(phi_pair, 2, 2, Qt.AlignHCenter)

        layout.addWidget(self.phase_confirm_btn, 3, 0, Qt.AlignLeft)
        layout.addWidget(self.auto_cal_btn, 3, 1, Qt.AlignLeft)
        layout.addWidget(self.data_send_btn, 3, 2, Qt.AlignLeft)
        layout.setRowMinimumHeight(4, 20)
        layout.setRowStretch(4, 1)

        self.phase_inputs = list(self.feed_phase_spins.values()) + [self.theta_spin, self.phi_spin, self.beam_checkbox]
        self._sync_phase_input_availability()
        return group

    def _field_pair(
        self,
        label_text: str,
        editor: QWidget,
        width: int,
        label_width: int | None = None,
        label_alignment: Qt.AlignmentFlag = Qt.AlignRight | Qt.AlignVCenter,
        label_indent: int = 0,
    ) -> QWidget:
        """创建 UI1 中常用的“标签 + 输入框”横向组合。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(label_text)
        if label_width is not None:
            label.setFixedWidth(label_width)
            label.setAlignment(label_alignment)
            label.setIndent(label_indent)
        layout.addWidget(label)
        layout.addWidget(editor)
        layout.addStretch(1)
        widget.setFixedWidth(width)
        return widget

    def _build_feedback_group(self) -> QGroupBox:
        """构建底部信息反馈窗，发送 HEX 和操作结果都会追加到这里。"""
        group = QGroupBox("信息反馈窗")
        group.setMinimumHeight(220)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(30, 18, 30, 16)
        self.feedback_edit = QTextEdit()
        self.feedback_edit.setPlaceholderText("")
        layout.addWidget(self.feedback_edit)
        return group

    def _initialize_button_states(self) -> None:
        """初始化成“重设/关闭”侧为选中态，匹配界面视觉设计。"""
        self._set_toggle_pair(self.basic_reset_btn, self.basic_confirm_btn)
        self._set_toggle_pair(self.lo_off_btn, self.lo_on_btn)
        self._set_toggle_pair(self.if_off_btn, self.if_on_btn)
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)

    def _reset_basic(self) -> None:
        """“基础设置-重设”按钮。

        重设基础参数会让已经确认的相位队列失效，因此同步清空 phase_queue，
        并恢复相位区域的可编辑状态。
        """
        if not self.basic_confirmed and self._basic_inputs_are_default():
            self._set_toggle_pair(self.basic_reset_btn, self.basic_confirm_btn)
            return

        self.output_freq_spin.setValue(DEFAULTS.frequency_ghz)
        self.basic_lo_power_spin.setValue(-20.0)
        self.basic_if_power_spin.setValue(-20.0)
        self.basic_confirmed = False
        self.phase_confirmed = False
        self.auto_calibrated = False
        self.phase_queue.clear()
        lock_widgets(self.basic_inputs, False)
        lock_widgets(self.phase_inputs, False)
        self._sync_phase_input_availability()
        self._set_toggle_pair(self.basic_reset_btn, self.basic_confirm_btn)
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
        self._feedback("基础设置已重设。")

    def _confirm_basic(self) -> None:
        """“基础设置-确认”按钮。

        这里目前只校验并锁定输出频率/功率输入，不直接向下位机发送本振/中频命令。
        输出频率会被波束配相公式读取，所以相位确认前至少要保证它有有效值。
        """
        if self.basic_confirmed:
            self._set_toggle_pair(self.basic_confirm_btn, self.basic_reset_btn)
            return

        values = self._read_required_spins(
            (
                (self.output_freq_spin, "输出频率"),
                (self.basic_lo_power_spin, "本振源功率"),
                (self.basic_if_power_spin, "中频源功率"),
            )
        )
        if values is None:
            self._set_toggle_pair(self.basic_reset_btn, self.basic_confirm_btn)
            return
        self.basic_confirmed = True
        lock_widgets(self.basic_inputs, True)
        self._set_toggle_pair(self.basic_confirm_btn, self.basic_reset_btn)
        freq, lo_power, if_power = values
        self._feedback(f"基础设置已确认：输出频率 {freq:g} GHz，本振 {lo_power:g} dBm，中频 {if_power:g} dBm。")

    def _refresh_serial_ports(self) -> None:
        """刷新 UI1 串口下拉框，保留当前选择优先。"""
        current = self.serial_combo.currentText() if hasattr(self, "serial_combo") else DEFAULTS.serial_port
        self.serial_combo.clear()
        ports = available_serial_ports(self.serial_port_default)
        self.serial_combo.addItems(ports)
        if current in ports:
            self.serial_combo.setCurrentText(current)

    def _connect_serial(self) -> None:
        """连接真实串口，并替换默认的设备控制器。

        默认配置可能是 simulated；用户点击“串口连接”后会强制创建 serial 模式的
        DeviceController，后续“数据发送”就会走真实 COM。
        """
        port = self.serial_combo.currentText().strip() or self.serial_port_default
        try:
            device = create_device_controller(port, mode=DEVICE_MODE_SERIAL)
            device.connect()
            self.device = device
            self._feedback(f"串口已连接：{port}")
        except Exception as exc:
            QMessageBox.warning(self, "串口连接失败", str(exc))

    def _initial_sync(self) -> None:
        """“初始同步”按钮。

        语义是把期望相位设为 0 deg，再叠加 UI0 校准表中的最佳相位偏移，
        直接写入 phase_queue。缺少校准表的馈源保持 0 deg。
        """
        if self.phase_confirmed:
            return

        zero_phases = {feed_id: 0.0 for feed_id in self.feed_phase_spins}
        calibrated, missing = self._apply_calibration_offsets(zero_phases)
        for feed_id, phase in calibrated.items():
            self.feed_phase_spins[feed_id].setValue(phase)
        self.theta_spin.setValue(0.0)
        self.phi_spin.setValue(0.0)
        self.phase_queue = self._build_phase_queue(calibrated)
        self.phase_confirmed = False
        self.auto_calibrated = True
        lock_widgets(self.phase_inputs, False)
        self._sync_phase_input_availability()
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
        if missing:
            self._feedback(f"初始同步成功，部分馈源缺少校准表，已使用 0 相位：{missing}。")
        else:
            self._feedback("初始同步成功，校准后的 0 相位数据已写入发送队列。")

    def _reset_phase_inputs(self) -> None:
        """“相位重设”按钮。

        恢复四馈源相位、θ0、φ0 和波束配相复选框默认值，同时清空已确认队列。
        """
        if not self.phase_confirmed and self._phase_inputs_are_default():
            self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
            return

        for spin in self.feed_phase_spins.values():
            spin.setValue(DEFAULT_FEED_PHASE_DEG)
        self.theta_spin.setValue(DEFAULT_BEAM_THETA_DEG)
        self.phi_spin.setValue(0.0)
        self.beam_checkbox.setChecked(False)
        self.phase_confirmed = False
        self.auto_calibrated = False
        self.phase_queue.clear()
        lock_widgets(self.phase_inputs, False)
        self._sync_phase_input_availability()
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
        self._feedback("相位输入已重设。")

    def _on_beam_checkbox_toggled(self, checked: bool) -> None:
        """切换“通过波束指向配相”时刷新输入可编辑状态。

        勾选后立即根据当前 θ0/频率计算四个馈源相位；取消勾选后用户可手动编辑相位。
        """
        self._sync_phase_input_availability()
        if checked and not self.phase_confirmed:
            self._update_beam_phase_values()

    def _sync_phase_input_availability(self) -> None:
        """根据当前模式同步相位区控件启用状态。

        - 已确认后：整组相位输入锁定，避免队列和界面显示不一致。
        - 波束配相：四个馈源相位锁定，θ0 可编辑，φ0 可编辑但不生效。
        - 手动模式：四个馈源相位可编辑，θ0 锁定。
        """
        if self.phase_confirmed:
            lock_widgets(self.phase_inputs, True)
            return

        use_beam = self.beam_checkbox.isChecked()
        for spin in self.feed_phase_spins.values():
            set_locked(spin, use_beam)
        set_locked(self.theta_spin, not use_beam)
        set_locked(self.phi_spin, False)
        set_locked(self.beam_checkbox, False)

    def _update_beam_phase_values(self, *_args: object) -> None:
        """在波束配相模式下刷新四个馈源相位显示。

        触发来源包括 θ0 改动、输出频率改动、勾选波束配相。
        """
        if self.phase_confirmed or not self.beam_checkbox.isChecked():
            return

        phases = self._calculate_beam_phases()
        for feed_id, phase in phases.items():
            self.feed_phase_spins[feed_id].setValue(phase)

    def _confirm_phase(self) -> bool:
        """“相位确认”按钮。

        手动模式读取四个相位输入；波束模式先按公式计算四个相位。
        最终都会写入 phase_queue，后续自动校准/数据发送都以 phase_queue 为准。
        """
        if self.phase_confirmed:
            self._set_toggle_pair(self.phase_confirm_btn, self.phase_reset_btn)
            return True

        if not self._has_required_basic():
            self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
            return False

        if self.beam_checkbox.isChecked():
            if self._read_required_spins(((self.theta_spin, "波束指向角度 θ₀"),)) is None:
                self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
                return False
            phases = self._calculate_beam_phases()
            for feed_id, phase in phases.items():
                self.feed_phase_spins[feed_id].setValue(phase)
        else:
            values = self._read_required_spins(
                tuple((spin, f"馈源{feed_id}相位配置") for feed_id, spin in self.feed_phase_spins.items())
            )
            if values is None:
                self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
                return False
            phases = dict(zip(self.feed_phase_spins.keys(), values))

        self.phase_queue = self._build_phase_queue(phases)
        self.phase_confirmed = True
        self.auto_calibrated = False
        lock_widgets(self.phase_inputs, True)
        self._set_toggle_pair(self.phase_confirm_btn, self.phase_reset_btn)
        self._feedback("相位配置已确认，数据已写入发送队列。")
        return True

    def _auto_calibrate(self) -> None:
        """“自动校准”按钮。

        自动校准会读取 UI0 生成的最佳相位表，把每个馈源的期望相位叠加对应
        最佳相位偏移。注意它会覆盖 phase_queue 中的相位。
        """
        if self.auto_calibrated:
            return

        if not self.phase_queue and not self._confirm_phase():
            return

        calibrated, missing = self._apply_calibration_offsets({state.feed_id: state.phase_deg for state in self.phase_queue})
        self.phase_queue = self._build_phase_queue(calibrated)
        self.auto_calibrated = True
        for feed_id, phase in calibrated.items():
            self.feed_phase_spins[feed_id].setValue(phase)

        detail = "；".join(f"馈源{state.feed_id}: {state.phase_deg:.3f} deg" for state in self.phase_queue)
        if missing:
            self._feedback(f"自动校准完成，部分馈源缺少校准表，已保留原相位：{missing}。当前发送队列：{detail}")
        else:
            self._feedback(f"自动校准完成，校准后的相位已写入发送队列：{detail}")

    def _send_data(self) -> None:
        """“数据发送”按钮。

        GUI 反馈窗保持用户配置视角；终端打印实际发送队列和完整 HEX。
        如果当前是 simulated 模式，会得到模拟 ACK；真实串口模式会写入 COM。
        """
        if not self.phase_queue:
            QMessageBox.warning(self, "发送失败", "请先执行相位确认或自动校准。")
            self._feedback("发送失败：发送队列为空。")
            return
        send_queue, _common_offset = self._build_send_queue_with_feed1_zero()
        frame = self.device.encode_feed_states(send_queue)
        print("实际发送数据：", flush=True)
        print(self._format_queue_payload(send_queue), flush=True)
        print(f"实际发送帧HEX：{frame.hex(' ')}", flush=True)
        self._feedback("发送数据：")
        self._feedback(self._format_queue_payload())
        response = self.device.apply_feed_states(send_queue)
        if response.ok:
            self._feedback("发送成功。")
        else:
            self._feedback(f"发送失败：{response.message}")
            QMessageBox.warning(self, "发送失败", response.message)

    def _calculate_beam_phases(self) -> dict[int, float]:
        """按波束指向角计算四个馈源相位。

        θ0 界面输入单位为 deg，这里先换算为 rad 再进入 sin()。
        返回值已经按 0~360 deg 取模；φ0 当前不参与计算。
        """
        frequency_hz = self.output_freq_spin.value() * GHZ_TO_HZ # 输出频率输入单位是 GHz，计算时需要换算成 Hz。
        theta_rad = self.theta_spin.value() * pi / 180.0
        base = (
            -(2.0 * pi * frequency_hz / LIGHT_SPEED_MPS)
            * sin(theta_rad)
            * FEED_SPACING_M
            * (180.0 / pi)
        )
        return {
            feed_id: (base * (feed_id - 1)) % 360.0
            for feed_id in (1, 2, 3, 4)
        }

    def _set_source_state(self, source: str, enabled: bool) -> None:
        """维护本振/中频按钮的 UI 状态。

        当前只做界面反馈，不向下位机发送独立开关命令；如果以后增加源控制命令，
        可从这里接入 DeviceController。
        """
        if source == "lo":
            if self.lo_enabled == enabled:
                self._set_toggle_pair(self.lo_on_btn if enabled else self.lo_off_btn, self.lo_off_btn if enabled else self.lo_on_btn)
                return

            self.lo_enabled = enabled
            self._set_toggle_pair(self.lo_on_btn if enabled else self.lo_off_btn, self.lo_off_btn if enabled else self.lo_on_btn)
            self._feedback("本振开启。" if enabled else "本振关闭。")
            return

        if self.if_enabled == enabled:
            self._set_toggle_pair(self.if_on_btn if enabled else self.if_off_btn, self.if_off_btn if enabled else self.if_on_btn)
            return

        self.if_enabled = enabled
        self._set_toggle_pair(self.if_on_btn if enabled else self.if_off_btn, self.if_off_btn if enabled else self.if_on_btn)
        self._feedback("中频开启。" if enabled else "中频关闭。")

    def _build_phase_queue(self, phases: dict[int, float]) -> list[FeedState]:
        """把相位字典转换为下发队列。

        所有相位统一按 0~360 deg 取模，并默认四个馈源都 enabled。
        """
        return [
            FeedState(feed_id=feed_id, phase_deg=phase % 360.0, amplitude=DEFAULTS.default_amplitude, enabled=True)
            for feed_id, phase in sorted(phases.items())
        ]

    def _build_send_queue_with_feed1_zero(self) -> tuple[list[FeedState], float]:
        """生成实际发送队列：Feed1 非 0 时四路同步偏置到 Feed1=0。"""
        feed1 = next((state for state in self.phase_queue if state.feed_id == 1), None)
        if feed1 is None:
            return list(self.phase_queue), 0.0

        feed1_phase = feed1.phase_deg % 360.0
        if abs(feed1_phase) < 1e-9:
            return list(self.phase_queue), 0.0

        common_offset = -feed1_phase
        return [
            FeedState(
                feed_id=state.feed_id,
                phase_deg=(state.phase_deg + common_offset) % 360.0,
                amplitude=state.amplitude,
                enabled=state.enabled,
            )
            for state in self.phase_queue
        ], common_offset

    def _format_queue_payload(self, feed_states: list[FeedState] | None = None) -> str:
        """格式化馈源队列，供信息反馈窗展示。"""
        queue = self.phase_queue if feed_states is None else feed_states
        lines = []
        for state in queue:
            lines.append(
                f"Feed{state.feed_id}: phase={state.phase_deg:.6f} deg, "
                f"enabled={state.enabled}"
            )
        return "\n".join(lines)

    def _apply_calibration_offsets(self, desired_phases: dict[int, float]) -> tuple[dict[int, float], list[int]]:
        """叠加 UI0 校准结果中的最佳相位偏移。

        desired_phases 表示用户或波束公式期望的相位；read_best_feed_point()
        读取的是各馈源校准时找到的最佳偏移。缺少表时返回 missing 列表。
        """
        calibrated: dict[int, float] = {}
        missing: list[int] = []
        for feed_id, desired_phase in desired_phases.items():
            best = self.exporter.read_best_feed_point(feed_id)
            if best is None:
                calibrated[feed_id] = desired_phase % 360.0
                missing.append(feed_id)
                continue
            calibrated[feed_id] = (desired_phase + best[0]) % 360.0
        return calibrated, missing

    def _has_required_basic(self) -> bool:
        """相位确认前至少要求输出频率有效，因为波束配相需要 f。"""
        return self._read_required_spins(((self.output_freq_spin, "输出频率"),)) is not None

    def _basic_inputs_are_default(self) -> bool:
        """判断基础设置是否仍为默认值，用于避免重复重设时切换按钮状态异常。"""
        return (
            self._spin_has_value(self.output_freq_spin, DEFAULTS.frequency_ghz)
            and self._spin_has_value(self.basic_lo_power_spin, -20.0)
            and self._spin_has_value(self.basic_if_power_spin, -20.0)
        )

    def _phase_inputs_are_default(self) -> bool:
        """判断相位区是否仍为默认值。"""
        return (
            all(self._spin_has_value(spin, DEFAULT_FEED_PHASE_DEG) for spin in self.feed_phase_spins.values())
            and self._spin_has_value(self.theta_spin, DEFAULT_BEAM_THETA_DEG)
            and self._spin_has_value(self.phi_spin, 0.0)
            and not self.beam_checkbox.isChecked()
        )

    def _spin_has_value(self, spin: QDoubleSpinBox, value: float) -> bool:
        """同时检查输入框非空和值相等，避免空文本被 value() 当成 0 误判。"""
        return bool(spin.lineEdit().text().strip()) and abs(spin.value() - value) < 1e-9

    def _read_required_spins(self, fields: tuple[tuple[QDoubleSpinBox, str], ...]) -> tuple[float, ...] | None:
        """读取一组必填数值框。

        QDoubleSpinBox 被用户清空文本时 value() 仍可能返回旧值，所以这里先检查
        lineEdit 文本是否为空。
        """
        values: list[float] = []
        for spin, label in fields:
            if not spin.lineEdit().text().strip():
                QMessageBox.warning(self, "参数未填写", f"请填写{label}。")
                self._feedback(f"参数未填写：{label}。")
                return None
            values.append(spin.value())
        return tuple(values)

    def _set_toggle_pair(self, active: QPushButton, inactive: QPushButton) -> None:
        """维护成对按钮的 checked 视觉状态。"""
        active.setChecked(True)
        inactive.setChecked(False)

    def _feedback(self, text: str) -> None:
        """向底部信息反馈窗追加一行文本。"""
        self.feedback_edit.append(text)
