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
from ..config import (
    DEFAULTS,
    DEVICE_MODE_SERIAL,
    OUTPUT_DIR,
    SIGNAL_SOURCE_CONTROL_AUTO,
    SIGNAL_SOURCE_CONTROL_MANUAL,
    TURNTABLE_MODE_SERIAL,
    create_device_controller,
    create_signal_source_controller,
    create_spectrum_analyzer,
    create_turntable_controller,
)
from ..data import ExcelExporter, FrequencyPlan
from ..models import FeedState, ScanConfig, default_feed_states
from .common import available_serial_ports, lock_widgets, make_line, make_spin
from .style import APP_STYLESHEET


class CalibrationTestWindow(QMainWindow):
    """UI0：馈源间相位校准数据测试窗口。

    主要流程：
    1. 设置全局频率/功率/波束角/保存目录。
    2. Feed1 做单馈源功率测试。
    3. Feed2~4 逐个扫描相位，前序馈源保持最佳相位。
    4. 每个阶段保存 Excel，Feed4 完成后生成最终汇总表。
    """

    def __init__(self, serial_port: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("馈源间相位校准数据测试")
        self.setFixedSize(1000, 740)
        self.setStyleSheet(APP_STYLESHEET)

        # exporter/output_dir 控制所有 Excel 输出位置；全局设置确认时会重新创建 exporter。
        self.exporter = ExcelExporter(output_dir=OUTPUT_DIR)
        self.output_dir = OUTPUT_DIR
        self.serial_port_default = serial_port or DEFAULTS.serial_port
        # latest_files 记录每个 Feed 最近一次生成的 Excel 文件，供“查看测试结果”提示。
        self.latest_files: dict[int, Path] = {}
        # best_feed_phases 缓存 Feed1~4 的最佳相位，后续 Feed 扫描会继承前序最佳相位。
        self.best_feed_phases: dict[int, float] = {}
        # device/analyzer 默认由配置决定是 simulated 还是真实设备。
        self.device = create_device_controller(self.serial_port_default)
        self.analyzer = create_spectrum_analyzer()
        self.device.connect()
        self.analyzer.connect()
        self.signal_source_controller = None
        self.turntable_port_default = DEFAULTS.turntable_port
        self.turntable = create_turntable_controller(self.turntable_port_default)
        # CalibrationEngine 是 UI0 的扫描执行器，UI 只负责收集参数和保存结果。
        self.engine = CalibrationEngine(self.device, self.analyzer)

        self._build_ui()

    def _build_ui(self) -> None:
        """组装 UI0 的三类区域：全局设置、Feed1 测试、Feed2~4 扫描。"""
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
        """构建全局设置区。

        这里的参数会在 _run_scan() 中读入 ScanConfig；点击“确认”后会锁定，
        防止扫描过程中修改频率或保存目录导致数据不一致。
        """
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
        self.turntable_combo = QComboBox()
        self.turntable_combo.setFixedWidth(110)
        self.refresh_turntable_btn = QPushButton("刷新")
        self.refresh_turntable_btn.setFixedWidth(78)
        self.refresh_turntable_btn.clicked.connect(self._refresh_turntable_ports)
        self.turntable_btn = QPushButton("转台连接")
        self.turntable_btn.setFixedWidth(92)
        self.turntable_btn.clicked.connect(self._connect_turntable)
        self._refresh_serial_ports()
        self._refresh_turntable_ports()

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

        turntable_row = QWidget(group)
        turntable_layout = QHBoxLayout(turntable_row)
        turntable_layout.setContentsMargins(0, 0, 0, 0)
        turntable_layout.setSpacing(10)
        turntable_layout.addWidget(QLabel("转台串口"))
        self.turntable_combo.setParent(group)
        turntable_layout.addWidget(self.turntable_combo)
        self.refresh_turntable_btn.setParent(group)
        turntable_layout.addWidget(self.refresh_turntable_btn)
        self.turntable_btn.setParent(group)
        turntable_layout.addWidget(self.turntable_btn)
        turntable_row.setFixedSize(370, 28)
        turntable_row.move(330, 56)

        self.global_confirm_btn.setParent(group)
        self.global_confirm_btn.move(848, 26)

        mid_col = QWidget(group)
        mid_layout = QVBoxLayout(mid_col)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.addWidget(self._field_pair("本振源功率（dBm）", self.lo_power_spin, 210, 130), alignment=Qt.AlignLeft)
        mid_col.setFixedSize(220, 28)
        mid_col.move(330, 88)

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
        right_col.move(560, 88)

        self.global_inputs = [
            self.freq_spin,
            self.lo_power_spin,
            self.if_power_spin,
            self.beam_spin,
            self.save_dir_edit,
            self.browse_btn,
            self.serial_combo,
            self.refresh_serial_btn,
            self.turntable_combo,
            self.refresh_turntable_btn,
        ]
        return group

    def _build_feed1_group(self) -> QGroupBox:
        """构建 Feed1 单馈源功率测试区。

        Feed1 不做范围扫描，开始测试时只下发当前输入的固定相位。
        """
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
        """构建 Feed2~4 的相位扫描区。

        每个 Feed 都有起/止/步长三个输入框，保存到 _scan_fields 里，
        _run_scan(feed_id) 会按 feed_id 取出对应范围。
        """
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
        """固定坐标放置 QLabel，用于复刻原始界面布局。"""
        label = QLabel(text, parent)
        if width is None:
            label.adjustSize()
        else:
            label.setFixedWidth(width)
        label.move(x, y)
        return label

    def _place_pair(self, parent: QWidget, text: str, editor: QWidget, x: int, y: int, label_width: int) -> None:
        """固定坐标放置“标签 + 输入框”组合。"""
        label = QLabel(text, parent)
        label.setFixedWidth(label_width)
        label.move(x, y + 2)
        editor.setParent(parent)
        editor.move(x + label_width + 8, y)

    def _field_pair(self, label_text: str, editor: QWidget, width: int, label_width: int | None = None) -> QWidget:
        """创建可放入布局的“标签 + 输入框”组合。"""
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
        """懒创建 Feed2~4 的扫描范围输入框映射。"""
        if not hasattr(self, "_scan_field_store"):
            self._scan_field_store = {}
        return self._scan_field_store

    def _reset_global(self) -> None:
        """重置全局设置，并清空所有已缓存最佳相位。

        频率/波束角/保存目录改变后，历史最佳相位可能不再适用，所以从 Feed1
        开始清空 best_feed_phases。
        """
        self._disconnect_signal_sources(suppress_errors=True)
        self.freq_spin.setValue(DEFAULTS.frequency_ghz)
        self.lo_power_spin.setValue(-20.0)
        self.if_power_spin.setValue(-20.0)
        self.beam_spin.setValue(DEFAULTS.beam_angle_deg)
        self.save_dir_edit.setText(str(OUTPUT_DIR))
        self._clear_best_phases_from(1)
        lock_widgets(self.global_inputs, False)
        self._refresh_serial_ports()
        self._refresh_turntable_ports()

    def _confirm_global(self) -> None:
        """确认全局设置并锁定输入。

        这里会按当前保存目录重新创建 ExcelExporter；后续扫描结果会写到该目录。
        """
        self.output_dir = Path(self.save_dir_edit.text())
        self.exporter = ExcelExporter(output_dir=self.output_dir)
        try:
            signal_source_text = self._prepare_signal_sources()
        except Exception as exc:
            QMessageBox.warning(self, "信号源控制失败", str(exc))
            return
        try:
            turntable_text = self._move_turntable_to_beam_angle()
        except Exception as exc:
            QMessageBox.warning(self, "转台控制失败", str(exc))
            return
        lock_widgets(self.global_inputs, True)
        self._message(f"全局设置已确认。\n\n{signal_source_text}\n\n{turntable_text}")

    def _prepare_signal_sources(self) -> str:
        frequencies = FrequencyPlan(DEFAULTS.signal_source_frequency_plan_path).lookup(self.freq_spin.value())
        lo_power_dbm = self.lo_power_spin.value()
        if_power_dbm = self.if_power_spin.value()
        settings_text = (
            f"本振源：{frequencies.lo_frequency_ghz:.9g} GHz，{lo_power_dbm:g} dBm\n"
            f"中频源：{frequencies.if_frequency_ghz:.9g} GHz，{if_power_dbm:g} dBm"
        )

        mode = DEFAULTS.signal_source_control_mode.strip().lower()
        if mode == SIGNAL_SOURCE_CONTROL_MANUAL:
            self._disconnect_signal_sources(suppress_errors=True)
            return f"信号源手动控制模式，未下发仪器命令。\n请手动设置：\n{settings_text}"
        if mode != SIGNAL_SOURCE_CONTROL_AUTO:
            raise ValueError(
                "signal_source_control_mode must be one of: "
                f"{SIGNAL_SOURCE_CONTROL_MANUAL}, {SIGNAL_SOURCE_CONTROL_AUTO}"
            )

        self._disconnect_signal_sources()
        controller = create_signal_source_controller()
        if controller is None:
            return f"信号源手动控制模式，未下发仪器命令。\n请手动设置：\n{settings_text}"

        try:
            controller.connect()
            controller.configure_sources(
                lo_frequency_ghz=frequencies.lo_frequency_ghz,
                lo_power_dbm=lo_power_dbm,
                if_frequency_ghz=frequencies.if_frequency_ghz,
                if_power_dbm=if_power_dbm,
                output_enabled=True,
            )
        except Exception:
            try:
                controller.disconnect()
            except Exception:
                pass
            raise

        self.signal_source_controller = controller
        return f"信号源自动控制已下发。\n{settings_text}"

    def _move_turntable_to_beam_angle(self) -> str:
        """把 UI0 的波束指向角作为转台目标角度执行一次定位。"""
        target_angle = self.beam_spin.value()
        step_angle = self.turntable.move_to_angle(target_angle)
        mode_text = "模拟转台（未连接真实转台）" if self.turntable.is_simulated else "真实转台"
        if abs(step_angle) <= 1e-9:
            return f"{mode_text}已在波束指向：{target_angle:g} deg。"
        return f"{mode_text}已转到波束指向：{target_angle:g} deg，本次转动：{step_angle:g} deg。"

    def _disconnect_signal_sources(self, suppress_errors: bool = False) -> None:
        if self.signal_source_controller is None:
            return
        try:
            self.signal_source_controller.disconnect()
        except Exception:
            if not suppress_errors:
                raise
        finally:
            self.signal_source_controller = None

    def _browse_output(self) -> None:
        """选择 Excel 输出目录。"""
        selected = QFileDialog.getExistingDirectory(self, "选择数据保存目录", self.save_dir_edit.text())
        if selected:
            self.save_dir_edit.setText(selected)

    def _refresh_serial_ports(self) -> None:
        """刷新串口下拉框，尽量保留用户当前选择。"""
        current = self.serial_combo.currentText() if hasattr(self, "serial_combo") else DEFAULTS.serial_port
        self.serial_combo.clear()
        ports = available_serial_ports(self.serial_port_default)
        self.serial_combo.addItems(ports)
        if current in ports:
            self.serial_combo.setCurrentText(current)

    def _refresh_turntable_ports(self) -> None:
        """刷新转台串口下拉框，尽量保留用户当前选择。"""
        current = self.turntable_combo.currentText() if hasattr(self, "turntable_combo") else DEFAULTS.turntable_port
        self.turntable_combo.clear()
        ports = available_serial_ports(self.turntable_port_default)
        self.turntable_combo.addItems(ports)
        if current in ports:
            self.turntable_combo.setCurrentText(current)

    def _connect_serial(self) -> None:
        """把 UI0 从默认设备切换到真实 STM32 串口设备。

        连接成功后必须重建 CalibrationEngine，因为 Engine 持有 DeviceController 引用。
        """
        port = self.serial_combo.currentText().strip() or self.serial_port_default
        try:
            device = create_device_controller(port, mode=DEVICE_MODE_SERIAL)
            device.connect()
            self.device = device
            self.engine = CalibrationEngine(self.device, self.analyzer)
            self._message(f"串口已连接：{port}")
        except Exception as exc:
            QMessageBox.warning(self, "串口连接失败", str(exc))

    def _connect_turntable(self) -> None:
        """连接真实转台串口，并把当前位置设为 0 deg。"""
        port = self.turntable_combo.currentText().strip() or self.turntable_port_default
        try:
            try:
                self.turntable.disconnect()
            except Exception:
                pass
            turntable = create_turntable_controller(port, mode=TURNTABLE_MODE_SERIAL)
            turntable.connect()
            self.turntable = turntable
            self._message(f"转台串口已连接并设零：{port}")
        except Exception as exc:
            QMessageBox.warning(self, "转台连接失败", str(exc))

    def _reset_scan_fields(self, feed_id: int) -> None:
        """重置某个 Feed 的扫描范围，并清空它及后续 Feed 的最佳相位。"""
        phase_start, phase_end, phase_step = self._scan_fields[feed_id]
        phase_start.setValue(DEFAULTS.phase_start_deg)
        phase_end.setValue(DEFAULTS.phase_end_deg)
        phase_step.setValue(DEFAULTS.phase_step_deg)
        self._clear_best_phases_from(feed_id)

    def _reset_feed1_phase(self) -> None:
        """重置 Feed1 固定相位，同时清空全部最佳相位缓存。"""
        self.feed1_phase_spin.setValue(0.0)
        self._clear_best_phases_from(1)

    def _confirm_feed1_phase(self) -> None:
        """手动确认 Feed1 初始相位，供后续 Feed2~4 扫描继承。"""
        self.best_feed_phases[1] = self.feed1_phase_spin.value()
        self._message("馈源1相位状态已确认。")

    def _clear_best_phases_from(self, feed_id: int) -> None:
        """从指定 Feed 开始清空最佳相位缓存。

        如果 Feed2 的扫描范围被改动，那么 Feed2/3/4 的历史最佳点都可能失效；
        但 Feed1 不受影响，所以从传入编号开始清理。
        """
        for current_feed_id in range(feed_id, DEFAULTS.feed_count + 1):
            self.best_feed_phases.pop(current_feed_id, None)

    def _feed_states_for_scan(self, target_feed_id: int) -> list[FeedState]:
        """为当前扫描目标生成四馈源下发状态。

        规则：
        - Feed1~target_feed_id 打开，后续 Feed 关闭。
        - 目标 Feed 的相位由 CalibrationEngine 在循环里覆盖。
        - 前序 Feed 优先使用内存缓存的最佳相位；没有缓存时读取 Excel 历史最佳点。
        """
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
        """“开始测试”按钮的统一入口。

        Feed1 是固定相位单点测试；Feed2~4 按界面起/止/步长扫描。
        扫描完成后保存对应 Excel，并把最佳相位缓存起来供下一阶段继承。
        """
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
            # Engine 负责下发/采样；UI 层负责保存结果和弹窗提示。
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
                # Feed4 完成代表四个馈源都有数据，可以生成最终汇总表。
                final_output = self.exporter.save_multi_feed_result(config.frequency_ghz, config.beam_angle_deg)
                text += f"\n最终汇总：{final_output.name}"
            self._message(text)
        except Exception as exc:
            QMessageBox.warning(self, "测试失败", str(exc))

    def _show_latest(self, feed_id: int) -> None:
        """显示最近一次生成的关联数据文件路径或默认文件名。"""
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
        """UI0 统一信息提示入口。"""
        QMessageBox.information(self, "提示", text)

    def closeEvent(self, event) -> None:
        self._disconnect_signal_sources(suppress_errors=True)
        try:
            self.turntable.disconnect()
        except Exception:
            pass
        super().closeEvent(event)
