from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace


def _install_pyside6_stub() -> None:
    class _Widget:
        pass

    class _QAbstractSpinBox(_Widget):
        class ButtonSymbols:
            NoButtons = 0

    class _Qt:
        AlignmentFlag = int
        AlignLeft = 1
        AlignRight = 2
        AlignVCenter = 4
        AlignTop = 8
        AlignCenter = 16
        AlignHCenter = 32

    pyside6 = ModuleType("PySide6")
    qt_core = ModuleType("PySide6.QtCore")
    qt_widgets = ModuleType("PySide6.QtWidgets")

    qt_core.Qt = _Qt
    qt_core.QTimer = _Widget
    widget_names = (
        "QCheckBox",
        "QComboBox",
        "QDoubleSpinBox",
        "QFileDialog",
        "QFrame",
        "QGridLayout",
        "QGroupBox",
        "QHBoxLayout",
        "QLabel",
        "QLineEdit",
        "QMainWindow",
        "QMessageBox",
        "QPushButton",
        "QTextEdit",
        "QVBoxLayout",
        "QWidget",
    )
    for name in widget_names:
        setattr(qt_widgets, name, _Widget)
    qt_widgets.QAbstractSpinBox = _QAbstractSpinBox

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qt_core
    sys.modules["PySide6.QtWidgets"] = qt_widgets


try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    _install_pyside6_stub()

from thz_calibration.ui import phase_config_window as phase_ui


def _phase_math_window() -> SimpleNamespace:
    window = SimpleNamespace()
    window._feed_is_enabled = lambda _feed_id: True
    window._normalize_feed_phase = phase_ui.PhaseConfigWindow._normalize_feed_phase.__get__(window)
    window._quantize_feed_phase_input = phase_ui.PhaseConfigWindow._quantize_feed_phase_input.__get__(window)
    return window


def test_ui1_feed_phase_range_excludes_360_deg() -> None:
    assert phase_ui.FEED_PHASE_MAX_DEG == 354.375
    assert phase_ui.PhaseConfigWindow._is_valid_feed_phase(None, 0.0)
    assert phase_ui.PhaseConfigWindow._is_valid_feed_phase(None, phase_ui.FEED_PHASE_MAX_DEG)
    assert not phase_ui.PhaseConfigWindow._is_valid_feed_phase(None, 360.0)


def test_ui1_computed_phase_wraps_360_deg_to_zero() -> None:
    window = _phase_math_window()

    assert phase_ui.PhaseConfigWindow._quantize_feed_phase(window, 360.0) == 0.0
    assert phase_ui.PhaseConfigWindow._quantize_feed_phase(window, 359.9) == 0.0
    assert phase_ui.PhaseConfigWindow._quantize_feed_phase(window, -5.625) == 354.375


def test_ui1_phase_queue_normalizes_360_before_send() -> None:
    window = _phase_math_window()

    states = phase_ui.PhaseConfigWindow._build_phase_queue(
        window,
        {
            1: 360.0,
            2: 720.0,
            3: 359.9999999,
            4: 354.375,
        },
    )

    assert [state.phase_deg for state in states] == [0.0, 0.0, 0.0, 354.375]
