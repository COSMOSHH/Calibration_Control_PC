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
from .common import available_serial_ports, lock_widgets, make_spin
from .style import APP_STYLESHEET


class PhaseConfigWindow(QMainWindow):
    def __init__(self, serial_port: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("分布式有源驱动馈源阵输出相位配置软件")
        self.setFixedSize(1280, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self.serial_port_default = serial_port or DEFAULTS.serial_port
        self.device = create_device_controller(self.serial_port_default)
        self.device.connect()
        self.exporter = ExcelExporter()
        self.phase_queue: list[FeedState] = []
        self.basic_confirmed = False
        self.phase_confirmed = False
        self.auto_calibrated = False
        self.lo_enabled = False
        self.if_enabled = False

        self._build_ui()
        self._initialize_button_states()

    def _build_ui(self) -> None:
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
        group = QGroupBox("基础设置")
        group.setFixedHeight(185)

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

        output_column = self._field_pair("输出频率（GHz）", self.output_freq_spin, 246)
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(24)
        left_layout.addWidget(self.basic_reset_btn, alignment=Qt.AlignLeft)
        left_layout.addWidget(output_column, alignment=Qt.AlignLeft)
        left_layout.addWidget(self.basic_confirm_btn, alignment=Qt.AlignLeft)
        left_column.setParent(group)
        left_column.move(28, 28)

        serial_panel = QWidget()
        serial_layout = QGridLayout(serial_panel)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.setHorizontalSpacing(10)
        serial_layout.setVerticalSpacing(12)
        serial_layout.addWidget(QLabel("串口"), 0, 0, Qt.AlignRight)
        serial_layout.addWidget(self.serial_combo, 0, 1)
        serial_layout.addWidget(self.refresh_serial_btn, 0, 2)
        serial_layout.addWidget(self.serial_btn, 1, 1, 1, 2, Qt.AlignLeft)
        serial_panel.setParent(group)
        serial_panel.move(970, 50)

        lo_column = self._basic_column(
            "本振源功率（dBm）",
            self.basic_lo_power_spin,
            self.lo_on_btn,
            self.lo_off_btn,
            286,
        )
        if_column = self._basic_column(
            "中频源功率（dBm）",
            self.basic_if_power_spin,
            self.if_on_btn,
            self.if_off_btn,
            286,
        )
        lo_column.setParent(group)
        if_column.setParent(group)
        lo_column.move(360, 64)
        if_column.move(650, 64)

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

    def _basic_column(
        self,
        label_text: str,
        editor: QWidget,
        left_button: QPushButton | None,
        right_button: QPushButton | None,
        width: int,
    ) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._field_pair(label_text, editor, width))
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
        group = QGroupBox("")
        group.setFixedHeight(310)
        layout = QGridLayout(group)
        layout.setContentsMargins(34, 22, 34, 18)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(20)

        self.initial_sync_btn = QPushButton("初始同步")
        self.phase_reset_btn = QPushButton("相位重设")
        self.beam_checkbox = QCheckBox("通过波束指向配相")
        self.phase_confirm_btn = QPushButton("相位确认")
        self.auto_cal_btn = QPushButton("自动校准")
        self.data_send_btn = QPushButton("数据发送")
        self.phase_reset_btn.setCheckable(True)
        self.phase_confirm_btn.setCheckable(True)

        self.initial_sync_btn.clicked.connect(self._initial_sync)
        self.phase_reset_btn.clicked.connect(self._reset_phase_inputs)
        self.phase_confirm_btn.clicked.connect(self._confirm_phase)
        self.auto_cal_btn.clicked.connect(self._auto_calibrate)
        self.data_send_btn.clicked.connect(self._send_data)

        layout.addWidget(self.initial_sync_btn, 0, 0)
        layout.addWidget(self.phase_reset_btn, 1, 0)
        layout.addWidget(self.beam_checkbox, 1, 1)

        self.feed_phase_spins = {}
        for index, feed_id in enumerate((1, 2, 3, 4)):
            feed_box = QWidget()
            feed_layout = QVBoxLayout(feed_box)
            feed_layout.setContentsMargins(0, 0, 0, 0)
            feed_layout.setSpacing(14)
            feed_label = QLabel(f"馈源{feed_id}")
            feed_label.setAlignment(Qt.AlignCenter)
            phase_spin = make_spin(30.0, 0, 360, 3, 96)
            self.feed_phase_spins[feed_id] = phase_spin
            feed_layout.addWidget(feed_label)
            feed_layout.addWidget(self._field_pair("相位配置（deg）", phase_spin, 250))
            layout.addWidget(feed_box, 2, index, Qt.AlignHCenter)
            layout.setColumnStretch(index, 1)

        self.theta_spin = make_spin(20.0, -180, 180, 3, 96)
        self.phi_spin = make_spin(0.0, -180, 180, 3, 96)
        layout.addWidget(self._field_pair("波束指向角度 θ₀（deg）", self.theta_spin, 300), 4, 0, 1, 2)
        layout.addWidget(self._field_pair("波束指向角度 φ₀（deg）", self.phi_spin, 300), 4, 2, 1, 2)

        layout.addWidget(self.phase_confirm_btn, 5, 0)
        layout.addWidget(self.auto_cal_btn, 5, 1)
        layout.addWidget(self.data_send_btn, 5, 2)

        self.phase_inputs = list(self.feed_phase_spins.values()) + [self.theta_spin, self.phi_spin, self.beam_checkbox]
        return group

    def _field_pair(self, label_text: str, editor: QWidget, width: int) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(label_text)
        layout.addWidget(label)
        layout.addWidget(editor)
        layout.addStretch(1)
        widget.setFixedWidth(width)
        return widget

    def _build_feedback_group(self) -> QGroupBox:
        group = QGroupBox("信息反馈窗")
        group.setMinimumHeight(220)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(30, 18, 30, 16)
        self.feedback_edit = QTextEdit()
        self.feedback_edit.setPlaceholderText("")
        layout.addWidget(self.feedback_edit)
        return group

    def _initialize_button_states(self) -> None:
        self._set_toggle_pair(self.basic_reset_btn, self.basic_confirm_btn)
        self._set_toggle_pair(self.lo_off_btn, self.lo_on_btn)
        self._set_toggle_pair(self.if_off_btn, self.if_on_btn)
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)

    def _reset_basic(self) -> None:
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
        self._set_toggle_pair(self.basic_reset_btn, self.basic_confirm_btn)
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
        self._feedback("基础设置已重设。")

    def _confirm_basic(self) -> None:
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
        current = self.serial_combo.currentText() if hasattr(self, "serial_combo") else DEFAULTS.serial_port
        self.serial_combo.clear()
        ports = available_serial_ports(self.serial_port_default)
        self.serial_combo.addItems(ports)
        if current in ports:
            self.serial_combo.setCurrentText(current)

    def _connect_serial(self) -> None:
        port = self.serial_combo.currentText().strip() or self.serial_port_default
        try:
            device = create_device_controller(port, mode=DEVICE_MODE_SERIAL)
            device.connect()
            self.device = device
            self._feedback(f"串口已连接：{port}")
        except Exception as exc:
            QMessageBox.warning(self, "串口连接失败", str(exc))

    def _initial_sync(self) -> None:
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
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
        if missing:
            self._feedback(f"初始同步成功，部分馈源缺少校准表，已使用 0 相位：{missing}。")
        else:
            self._feedback("初始同步成功，校准后的 0 相位数据已写入发送队列。")

    def _reset_phase_inputs(self) -> None:
        if not self.phase_confirmed and self._phase_inputs_are_default():
            self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
            return

        for spin in self.feed_phase_spins.values():
            spin.setValue(30.0)
        self.theta_spin.setValue(20.0)
        self.phi_spin.setValue(0.0)
        self.beam_checkbox.setChecked(False)
        self.phase_confirmed = False
        self.auto_calibrated = False
        self.phase_queue.clear()
        lock_widgets(self.phase_inputs, False)
        self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
        self._feedback("相位输入已重设。")

    def _confirm_phase(self) -> bool:
        if self.phase_confirmed:
            self._set_toggle_pair(self.phase_confirm_btn, self.phase_reset_btn)
            return True

        if not self._has_required_basic():
            self._set_toggle_pair(self.phase_reset_btn, self.phase_confirm_btn)
            return False

        if self.beam_checkbox.isChecked():
            if self._read_required_spins(((self.theta_spin, "波束指向角度 θ₀"), (self.phi_spin, "波束指向角度 φ₀"))) is None:
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
        if not self.phase_queue:
            QMessageBox.warning(self, "发送失败", "请先执行相位确认或自动校准。")
            self._feedback("发送失败：发送队列为空。")
            return
        frame = self.device.encode_feed_states(self.phase_queue)
        self._feedback("发送数据：")
        self._feedback(self._format_queue_payload())
        self._feedback(f"发送帧HEX：{frame.hex(' ')}")
        response = self.device.apply_feed_states(self.phase_queue)
        if response.ok:
            self._feedback("发送成功。")
        else:
            self._feedback(f"发送失败：{response.message}")
            QMessageBox.warning(self, "发送失败", response.message)

    def _calculate_beam_phases(self) -> dict[int, float]:
        theta = self.theta_spin.value()
        phi0 = self.phi_spin.value()
        spacing_mm = 15.52
        wavelength_mm = 300.0 / self.output_freq_spin.value()
        base = -360.0 * spacing_mm * sin(theta * pi / 180.0) / wavelength_mm
        return {
            feed_id: (phi0 + base * (feed_id - 1)) % 360.0
            for feed_id in (1, 2, 3, 4)
        }

    def _set_source_state(self, source: str, enabled: bool) -> None:
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
        return [
            FeedState(feed_id=feed_id, phase_deg=phase % 360.0, amplitude=DEFAULTS.default_amplitude, enabled=True)
            for feed_id, phase in sorted(phases.items())
        ]

    def _format_queue_payload(self) -> str:
        lines = []
        for state in self.phase_queue:
            lines.append(
                f"Feed{state.feed_id}: phase={state.phase_deg:.6f} deg, "
                f"enabled={state.enabled}"
            )
        return "\n".join(lines)

    def _apply_calibration_offsets(self, desired_phases: dict[int, float]) -> tuple[dict[int, float], list[int]]:
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
        return self._read_required_spins(((self.output_freq_spin, "输出频率"),)) is not None

    def _basic_inputs_are_default(self) -> bool:
        return (
            self._spin_has_value(self.output_freq_spin, DEFAULTS.frequency_ghz)
            and self._spin_has_value(self.basic_lo_power_spin, -20.0)
            and self._spin_has_value(self.basic_if_power_spin, -20.0)
        )

    def _phase_inputs_are_default(self) -> bool:
        return (
            all(self._spin_has_value(spin, 30.0) for spin in self.feed_phase_spins.values())
            and self._spin_has_value(self.theta_spin, 20.0)
            and self._spin_has_value(self.phi_spin, 0.0)
            and not self.beam_checkbox.isChecked()
        )

    def _spin_has_value(self, spin: QDoubleSpinBox, value: float) -> bool:
        return bool(spin.lineEdit().text().strip()) and abs(spin.value() - value) < 1e-9

    def _read_required_spins(self, fields: tuple[tuple[QDoubleSpinBox, str], ...]) -> tuple[float, ...] | None:
        values: list[float] = []
        for spin, label in fields:
            if not spin.lineEdit().text().strip():
                QMessageBox.warning(self, "参数未填写", f"请填写{label}。")
                self._feedback(f"参数未填写：{label}。")
                return None
            values.append(spin.value())
        return tuple(values)

    def _set_toggle_pair(self, active: QPushButton, inactive: QPushButton) -> None:
        active.setChecked(True)
        inactive.setChecked(False)

    def _feedback(self, text: str) -> None:
        self.feedback_edit.append(text)
