from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..calibration import CalibrationEngine
from ..config import DEFAULTS, DEVICE_MODE_SERIAL, OUTPUT_DIR, create_device_controller, create_spectrum_analyzer
from ..data import ExcelExporter
from ..models import FeedState, ScanConfig, default_feed_states
from .common import available_serial_ports, lock_widgets, make_line, make_spin
from .style import APP_STYLESHEET


class CalibrationTestWindow(QMainWindow):
    def __init__(self, serial_port: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("馈源间相位校准数据测试")
        self.setFixedSize(1000, 740)
        self.setStyleSheet(APP_STYLESHEET)

        self.exporter = ExcelExporter(output_dir=OUTPUT_DIR)
        self.output_dir = OUTPUT_DIR
        self.serial_port_default = serial_port or DEFAULTS.serial_port
        self.latest_files: dict[int, Path] = {}
        self.best_feed_phases: dict[int, float] = {}
        self.device = create_device_controller(self.serial_port_default)
        self.analyzer = create_spectrum_analyzer()
        self.device.connect()
        self.analyzer.connect()
        self.engine = CalibrationEngine(self.device, self.analyzer)

        self._build_ui()

    def _build_ui(self) -> None:
        shell = QFrame()
        shell.setObjectName("Shell")
        self.setCentralWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(18, 2, 18, 10)
        root.setSpacing(5)

        title = QLabel("馈源间相位校准数据测试")
        title.setObjectName("WindowTitle")
        title.setFixedHeight(24)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        root.addWidget(self._build_global_group())
        root.addWidget(self._build_feed1_group())
        for feed_id in (2, 3, 4):
            root.addWidget(self._build_feed_scan_group(feed_id))

    def _build_global_group(self) -> QGroupBox:
        group = QGroupBox("全局设置")
        group.setFixedHeight(150)

        self.global_reset_btn = QPushButton("重 设")
        self.global_reset_btn.setFixedWidth(92)
        self.global_reset_btn.clicked.connect(self._reset_global)

        self.freq_spin = make_spin(DEFAULTS.frequency_ghz, 1, 1000, 3, 58)
        self.lo_power_spin = make_spin(-20.0, -100, 30, 2, 58)
        self.if_power_spin = make_spin(-20.0, -100, 30, 2, 58)
        self.beam_spin = make_spin(DEFAULTS.beam_angle_deg, -180, 180, 2, 58)
        self.save_dir_edit = make_line(str(self.output_dir), 210)
        self.save_dir_edit.setReadOnly(True)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setFixedWidth(68)
        self.browse_btn.clicked.connect(self._browse_output)
        self.global_confirm_btn = QPushButton("确 认")
        self.global_confirm_btn.setFixedWidth(92)
        self.global_confirm_btn.clicked.connect(self._confirm_global)
        self.serial_combo = QComboBox()
        self.serial_combo.setFixedWidth(110)
        self.refresh_serial_btn = QPushButton("刷新")
        self.refresh_serial_btn.setFixedWidth(78)
        self.refresh_serial_btn.clicked.connect(self._refresh_serial_ports)
        self.serial_btn = QPushButton("串口连接")
        self.serial_btn.setFixedWidth(92)
        self.serial_btn.clicked.connect(self._connect_serial)
        self._refresh_serial_ports()

        left_col = QWidget(group)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(13)
        left_layout.addWidget(self.global_reset_btn, alignment=Qt.AlignLeft)
        left_layout.addWidget(self._field_pair("校准频率（GHz）", self.freq_spin, 205, 112), alignment=Qt.AlignLeft)
        left_layout.addWidget(self._field_pair("波束指向（deg）", self.beam_spin, 205, 112), alignment=Qt.AlignLeft)
        left_col.setFixedSize(225, 112)
        left_col.move(24, 26)

        serial_row = QWidget(group)
        serial_layout = QHBoxLayout(serial_row)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.setSpacing(10)
        serial_layout.addWidget(QLabel("串口"))
        self.serial_combo.setParent(group)
        serial_layout.addWidget(self.serial_combo)
        self.refresh_serial_btn.setParent(group)
        serial_layout.addWidget(self.refresh_serial_btn)
        self.serial_btn.setParent(group)
        serial_layout.addWidget(self.serial_btn)
        serial_row.setFixedSize(345, 28)
        serial_row.move(330, 26)

        self.global_confirm_btn.setParent(group)
        self.global_confirm_btn.move(848, 26)

        mid_col = QWidget(group)
        mid_layout = QVBoxLayout(mid_col)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.addWidget(self._field_pair("本振源功率（dBm）", self.lo_power_spin, 210, 130), alignment=Qt.AlignLeft)
        mid_col.setFixedSize(220, 28)
        mid_col.move(330, 73)

        right_col = QWidget(group)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(9)
        right_layout.addWidget(self._field_pair("中频源功率（dBm）", self.if_power_spin, 210, 130), alignment=Qt.AlignLeft)
        save_row = QWidget()
        save_layout = QHBoxLayout(save_row)
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.setSpacing(6)
        save_label = QLabel("数据保存目录")
        save_label.setFixedWidth(82)
        save_layout.addWidget(save_label)
        save_layout.addWidget(self.save_dir_edit)
        save_layout.addWidget(self.browse_btn)
        right_layout.addWidget(save_row)
        right_col.setFixedSize(380, 58)
        right_col.move(560, 73)

        self.global_inputs = [
            self.freq_spin,
            self.lo_power_spin,
            self.if_power_spin,
            self.beam_spin,
            self.save_dir_edit,
            self.browse_btn,
            self.serial_combo,
            self.refresh_serial_btn,
        ]
        return group

    def _build_feed1_group(self) -> QGroupBox:
        group = QGroupBox("馈源1功率测试")
        group.setFixedHeight(120)

        reset = QPushButton("重 设")
        reset.setFixedWidth(100)
        reset.clicked.connect(self._reset_feed1_phase)
        self.feed1_phase_spin = make_spin(0.0, 0, 360, 3, 58)
        confirm = QPushButton("确 认")
        confirm.setFixedWidth(72)
        confirm.clicked.connect(self._confirm_feed1_phase)
        start = QPushButton("开始测试")
        start.setFixedWidth(100)
        start.clicked.connect(lambda: self._run_scan(1))
        view = QPushButton("查看测试结果")
        view.setFixedWidth(130)
        view.clicked.connect(lambda: self._show_latest(1))

        reset.setParent(group)
        reset.move(20, 28)
        self._place_pair(group, "馈源1相位状态选择φp1（deg）", self.feed1_phase_spin, 610, 48, 218)
        confirm.setParent(group)
        confirm.move(831, 78)
        start.setParent(group)
        start.move(20, 88)
        view.setParent(group)
        view.move(130, 88)
        return group

    def _build_feed_scan_group(self, feed_id: int) -> QGroupBox:
        group = QGroupBox(f"馈源{feed_id}相位状态数据测试")
        group.setFixedHeight(120)

        reset = QPushButton("重 设")
        reset.setFixedWidth(100)
        start = QPushButton("开始测试")
        start.setFixedWidth(100)
        view = QPushButton("查看测试结果")
        view.setFixedWidth(130)
        confirm = QPushButton("确 认")
        confirm.setFixedWidth(72)
        phase_start = make_spin(DEFAULTS.phase_start_deg, 0, 360, 3, 58)
        phase_end = make_spin(DEFAULTS.phase_end_deg, 0, 360, 3, 72)
        phase_step = make_spin(DEFAULTS.phase_step_deg, 0.001, 360, 3, 64)
        self._scan_fields[feed_id] = (phase_start, phase_end, phase_step)

        reset.clicked.connect(lambda: self._reset_scan_fields(feed_id))
        confirm.clicked.connect(lambda: self._message(f"馈源{feed_id}相位搜索范围已确认。"))
        start.clicked.connect(lambda: self._run_scan(feed_id))
        view.clicked.connect(lambda: self._show_latest(feed_id))

        reset.setParent(group)
        reset.move(20, 28)
        self._place_label(group, f"馈源{feed_id}相位状态φp{feed_id}（deg）", 270, 52, 190)
        self._place_label(group, "搜寻范围", 470, 52, 76)
        self._place_label(group, "起", 552, 52, 20)
        phase_start.setParent(group)
        phase_start.move(585, 50)
        self._place_label(group, "止", 665, 52, 20)
        phase_end.setParent(group)
        phase_end.move(695, 50)
        self._place_label(group, "步长", 790, 52, 42)
        phase_step.setParent(group)
        phase_step.move(835, 50)
        confirm.setParent(group)
        confirm.move(831, 78)
        start.setParent(group)
        start.move(20, 88)
        view.setParent(group)
        view.move(130, 88)
        return group

    def _place_label(self, parent: QWidget, text: str, x: int, y: int, width: int | None = None) -> QLabel:
        label = QLabel(text, parent)
        if width is None:
            label.adjustSize()
        else:
            label.setFixedWidth(width)
        label.move(x, y)
        return label

    def _place_pair(self, parent: QWidget, text: str, editor: QWidget, x: int, y: int, label_width: int) -> None:
        label = QLabel(text, parent)
        label.setFixedWidth(label_width)
        label.move(x, y + 2)
        editor.setParent(parent)
        editor.move(x + label_width + 8, y)

    def _field_pair(self, label_text: str, editor: QWidget, width: int, label_width: int | None = None) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        if label_width is not None:
            label.setFixedWidth(label_width)
        layout.addWidget(label)
        layout.addWidget(editor)
        layout.addStretch(1)
        widget.setFixedWidth(width)
        return widget

    @property
    def _scan_fields(self) -> dict[int, tuple[QDoubleSpinBox, QDoubleSpinBox, QDoubleSpinBox]]:
        if not hasattr(self, "_scan_field_store"):
            self._scan_field_store = {}
        return self._scan_field_store

    def _reset_global(self) -> None:
        self.freq_spin.setValue(DEFAULTS.frequency_ghz)
        self.lo_power_spin.setValue(-20.0)
        self.if_power_spin.setValue(-20.0)
        self.beam_spin.setValue(DEFAULTS.beam_angle_deg)
        self.save_dir_edit.setText(str(OUTPUT_DIR))
        self._clear_best_phases_from(1)
        lock_widgets(self.global_inputs, False)
        self._refresh_serial_ports()

    def _confirm_global(self) -> None:
        self.output_dir = Path(self.save_dir_edit.text())
        self.exporter = ExcelExporter(output_dir=self.output_dir)
        lock_widgets(self.global_inputs, True)
        self._message("全局设置已确认。")

    def _browse_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择数据保存目录", self.save_dir_edit.text())
        if selected:
            self.save_dir_edit.setText(selected)

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
            self.engine = CalibrationEngine(self.device, self.analyzer)
            self._message(f"串口已连接：{port}")
        except Exception as exc:
            QMessageBox.warning(self, "串口连接失败", str(exc))

    def _reset_scan_fields(self, feed_id: int) -> None:
        phase_start, phase_end, phase_step = self._scan_fields[feed_id]
        phase_start.setValue(DEFAULTS.phase_start_deg)
        phase_end.setValue(DEFAULTS.phase_end_deg)
        phase_step.setValue(DEFAULTS.phase_step_deg)
        self._clear_best_phases_from(feed_id)

    def _reset_feed1_phase(self) -> None:
        self.feed1_phase_spin.setValue(0.0)
        self._clear_best_phases_from(1)

    def _confirm_feed1_phase(self) -> None:
        self.best_feed_phases[1] = self.feed1_phase_spin.value()
        self._message("馈源1相位状态已确认。")

    def _clear_best_phases_from(self, feed_id: int) -> None:
        for current_feed_id in range(feed_id, DEFAULTS.feed_count + 1):
            self.best_feed_phases.pop(current_feed_id, None)

    def _feed_states_for_scan(self, target_feed_id: int) -> list[FeedState]:
        states = default_feed_states(enabled_feeds=range(1, target_feed_id + 1))
        for state in states:
            if state.feed_id >= target_feed_id:
                continue

            best_phase = self.best_feed_phases.get(state.feed_id)
            if best_phase is None:
                best = self.exporter.read_best_feed_point(state.feed_id)
                if best is not None:
                    best_phase = best[0]
                    self.best_feed_phases[state.feed_id] = best_phase

            if best_phase is not None:
                state.phase_deg = best_phase
                state.amplitude = DEFAULTS.default_amplitude
        return states

    def _run_scan(self, feed_id: int) -> None:
        if feed_id == 1:
            phase_start = self.feed1_phase_spin.value()
            phase_end = self.feed1_phase_spin.value()
            phase_step = DEFAULTS.phase_step_deg
        else:
            phase_start, phase_end, phase_step = self._scan_fields[feed_id]
            phase_start = phase_start.value()
            phase_end = phase_end.value()
            phase_step = phase_step.value()

        config = ScanConfig(
            target_feed_id=feed_id,
            frequency_ghz=self.freq_spin.value(),
            beam_angle_deg=self.beam_spin.value(),
            phase_start_deg=phase_start,
            phase_end_deg=phase_end,
            phase_step_deg=phase_step,
            amplitude=DEFAULTS.default_amplitude,
            settle_time_ms=DEFAULTS.settle_time_ms,
            sample_count=DEFAULTS.sample_count,
        )
        try:
            result = self.engine.scan_feed(config, self._feed_states_for_scan(feed_id), on_log=lambda _: None)
            output = self.exporter.save_scan_result(result)
            self.latest_files[feed_id] = output
            best = result.best_point
            text = f"馈源{feed_id}测试完成。"
            if best:
                self.best_feed_phases[feed_id] = best.phase_deg
                text += f"\n最佳相位：{best.phase_deg:g} deg\n功率：{best.average_power_uw:.6f} uW"
            text += f"\n\n{output.name}"
            if feed_id == DEFAULTS.feed_count:
                final_output = self.exporter.save_multi_feed_result(config.frequency_ghz, config.beam_angle_deg)
                text += f"\n最终汇总：{final_output.name}"
            self._message(text)
        except Exception as exc:
            QMessageBox.warning(self, "测试失败", str(exc))

    def _show_latest(self, feed_id: int) -> None:
        output = self.latest_files.get(feed_id)
        if output:
            self._message(f"关联数据文件：\n{output}")
            return

        names = {
            1: "TestData_Feed1_BDp30_212",
            2: "CalProcess_Feed2wrt1_BDp30_212",
            3: "CalProcess_Feed3wrt12_BDp30_212",
            4: "CalProcess_Feed4wrt123_BDp30_212",
        }
        self._message(f"关联数据文件：\n{names[feed_id]}")

    def _message(self, text: str) -> None:
        QMessageBox.information(self, "提示", text)
