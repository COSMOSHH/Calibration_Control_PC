from __future__ import annotations

import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from debug_spectrum_analyzer import (  # noqa: E402
    drain_errors,
    make_io,
    open_instrument,
    print_actual_value,
    print_section,
    print_setpoint_check,
    query_float,
)
from thz_calibration.config import DEFAULTS  # noqa: E402
from thz_calibration.instruments.spectrum_analyzer import (  # noqa: E402
    _average_count_commands,
    _mapped_sweep_settings,
    _sweep_settings_commands,
)


MARKER_SETTLE_S = 0.5


def _require_ok(ok: bool, action: str) -> None:
    if not ok:
        raise RuntimeError(f"{action}失败，已停止单次测试。")


def _require_number(value: float | None, name: str) -> float:
    if value is None:
        raise RuntimeError(f"{name}读取失败，已停止单次测试。")
    return value


def _print_default_settings(settings) -> None:
    print_section("默认测试参数")
    print(f"address        : {DEFAULTS.visa_address}")
    print(f"cal center GHz : {DEFAULTS.frequency_ghz}")
    print(f"cal span GHz   : {DEFAULTS.spectrum_analyzer_span_ghz}")
    print(f"divisor        : {DEFAULTS.spectrum_analyzer_frequency_divisor}")
    print(f"SA start GHz   : {settings.start_ghz}")
    print(f"SA stop GHz    : {settings.stop_ghz}")
    print(f"sweep points   : {settings.points}")
    print("sweep time     : analyzer default (read back only)")
    print(f"RBW            : {settings.rbw_hz} Hz")
    print(f"VBW            : {settings.vbw_hz} Hz")
    print(f"average count  : {DEFAULTS.sample_count}")
    print(f"timeout ms     : {DEFAULTS.spectrum_analyzer_timeout_ms}")


def _write_sweep_settings(write, query, settings) -> None:
    print_section("设置并回读扫频参数")
    for command in _sweep_settings_commands(settings):
        _require_ok(write(command), command)

    actual_start_hz = query_float(query, "SENSe:FREQuency:STARt?")
    actual_stop_hz = query_float(query, "SENSe:FREQuency:STOP?")
    actual_points = query_float(query, "SENSe:SWEep:POINts?")
    actual_sweep_time = query_float(query, "SENSe:SWEep:TIME?")
    actual_rbw_hz = query_float(query, "SENSe:BANDwidth:RESolution?")
    actual_vbw_hz = query_float(query, "SENSe:BANDwidth:VIDeo?")

    print_setpoint_check("起始频率", settings.start_ghz * 1e9, actual_start_hz)
    print_setpoint_check("终止频率", settings.stop_ghz * 1e9, actual_stop_hz)
    print_setpoint_check("扫描点数", float(settings.points), actual_points, "点", abs_tolerance=0.5)
    print_actual_value("仪器实际扫频时间", actual_sweep_time, "s")
    print_setpoint_check("RBW", settings.rbw_hz, actual_rbw_hz)
    print_setpoint_check("VBW", settings.vbw_hz, actual_vbw_hz)


def _run_single_sweep(write, query) -> None:
    print_section("单次扫描并读取 Marker")
    _require_ok(write("INITiate:CONTinuous OFF"), "关闭连续扫描")
    _require_ok(write("CALCulate:MARKer1:STATe ON"), "开启 Marker1")
    _require_ok(write("INITiate:IMMediate"), "启动单次扫描")
    opc = query("*OPC?")
    if opc is None:
        raise RuntimeError("*OPC? 读取失败，无法确认单次扫描完成。")

    _require_ok(write("CALCulate:MARKer1:MAXimum"), "Marker 寻峰")
    time.sleep(MARKER_SETTLE_S)
    marker_freq_hz = _require_number(query_float(query, "CALCulate:MARKer1:X?"), "Marker 频率")
    marker_power_dbm = _require_number(query_float(query, "CALCulate:MARKer1:Y?"), "Marker 功率")
    print(f"Marker 频率: {marker_freq_hz / 1e9:.9f} GHz")
    print(f"Marker 功率: {marker_power_dbm:.6f} dBm")


def run_once() -> None:
    if DEFAULTS.spectrum_analyzer_frequency_divisor <= 0:
        raise ValueError("spectrum_analyzer_frequency_divisor must be positive")
    if DEFAULTS.spectrum_analyzer_scan_points <= 0:
        raise ValueError("spectrum_analyzer_scan_points must be positive")
    if DEFAULTS.spectrum_analyzer_rbw_hz <= 0:
        raise ValueError("spectrum_analyzer_rbw_hz must be positive")
    if DEFAULTS.spectrum_analyzer_vbw_hz <= 0:
        raise ValueError("spectrum_analyzer_vbw_hz must be positive")
    if DEFAULTS.sample_count <= 0:
        raise ValueError("sample_count must be positive")

    try:
        import pyvisa
    except ImportError as exc:
        raise RuntimeError("当前环境缺少 pyvisa，请先安装 pyvisa。") from exc

    settings = _mapped_sweep_settings(
        DEFAULTS.frequency_ghz,
        DEFAULTS.spectrum_analyzer_span_ghz,
        DEFAULTS.spectrum_analyzer_frequency_divisor,
        DEFAULTS.spectrum_analyzer_scan_points,
        DEFAULTS.spectrum_analyzer_rbw_hz,
        DEFAULTS.spectrum_analyzer_vbw_hz,
    )
    _print_default_settings(settings)

    rm = None
    instrument = None
    try:
        print_section("连接频谱仪")
        rm, instrument, opened_address = open_instrument(
            pyvisa,
            DEFAULTS.visa_address,
            DEFAULTS.spectrum_analyzer_timeout_ms,
        )
        query, write = make_io(instrument)

        print_section("设备识别")
        identity = query("*IDN?")
        if identity is None:
            raise RuntimeError("*IDN? 读取失败，已停止单次测试。")
        drain_errors(query, "连接后错误队列")

        _write_sweep_settings(write, query, settings)
        for command in _average_count_commands(DEFAULTS.sample_count):
            _require_ok(write(command), command)
        drain_errors(query, "参数设置后错误队列")
        _run_single_sweep(write, query)
        drain_errors(query, "单次测试后错误队列")

        print_section("完成")
        print(f"实际打开资源名: {opened_address}")
        print("默认参数单次频谱仪测试完成。")
    finally:
        if instrument is not None:
            instrument.close()
        if rm is not None:
            rm.close()


if __name__ == "__main__":
    run_once()
