from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from thz_calibration.config import DEFAULTS
from thz_calibration.instruments.spectrum_analyzer import (
    _mapped_sweep_settings,
    _sweep_settings_commands,
    _visa_resource_candidates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="频谱仪 VISA/SCPI 直连诊断脚本")
    parser.add_argument("--address", default=DEFAULTS.visa_address, help="VISA 资源地址，默认读取 config.py")
    parser.add_argument("--center-ghz", type=float, default=DEFAULTS.frequency_ghz, help="校准频率，单位 GHz")
    parser.add_argument("--span-ghz", type=float, default=DEFAULTS.spectrum_analyzer_span_ghz, help="校准扫宽，单位 GHz")
    parser.add_argument(
        "--sweep-points",
        type=int,
        default=DEFAULTS.spectrum_analyzer_scan_points,
        help="频率扫描点数，默认读取 config.py",
    )
    parser.add_argument(
        "--rbw-hz",
        "--if-bandwidth-hz",
        dest="rbw_hz",
        type=float,
        default=DEFAULTS.spectrum_analyzer_rbw_hz,
        help="分辨率带宽 RBW（Resolution Bandwidth），单位 Hz",
    )
    parser.add_argument(
        "--vbw-hz",
        dest="vbw_hz",
        type=float,
        default=DEFAULTS.spectrum_analyzer_vbw_hz,
        help="视频带宽 VBW（Video Bandwidth），单位 Hz",
    )
    parser.add_argument(
        "--frequency-divisor",
        type=float,
        default=DEFAULTS.spectrum_analyzer_frequency_divisor,
        help="频谱仪观察频率换算系数；无扩频模块调试用 10，接扩频模块用 1",
    )
    parser.add_argument("--timeout-ms", type=int, default=10000, help="VISA 超时时间，单位 ms")
    parser.add_argument("--settle-s", type=float, default=0.5, help="marker 寻峰后等待时间，单位秒")
    parser.add_argument("--skip-configure", action="store_true", help="只读取当前屏幕状态，不下发扫频参数")
    return parser.parse_args()


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def open_instrument(pyvisa_module, address: str, timeout_ms: int):
    rm = pyvisa_module.ResourceManager()
    print(f"PyVISA ResourceManager: {rm}")
    try:
        resources = rm.list_resources()
    except Exception as exc:
        resources = ()
        print(f"列出 VISA 资源失败: {exc}")

    print("当前可见 VISA 资源:")
    if resources:
        for resource in resources:
            print(f"  - {resource}")
    else:
        print("  - 无")

    candidates = _visa_resource_candidates(address)
    print("\n准备尝试资源名:")
    for candidate in candidates:
        print(f"  - {candidate}")

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            instrument = rm.open_resource(candidate)
            instrument.timeout = timeout_ms
            if candidate.upper().endswith("::SOCKET"):
                instrument.write_termination = "\n"
                instrument.read_termination = "\n"
            print(f"\n已连接: {candidate}")
            return rm, instrument, candidate
        except Exception as exc:
            last_error = exc
            print(f"连接失败: {candidate}")
            print(f"  {exc}")

    rm.close()
    raise RuntimeError(f"所有资源名均连接失败，最后错误: {last_error}")


def make_io(instrument) -> tuple[Callable[[str], str | None], Callable[[str], bool]]:
    def query(command: str) -> str | None:
        print(f">> {command}")
        try:
            response = str(instrument.query(command)).strip()
            print(f"<< {response}")
            return response
        except Exception as exc:
            print(f"<< 查询失败: {exc}")
            return None

    def write(command: str) -> bool:
        print(f">> {command}")
        try:
            instrument.write(command)
            print("<< OK")
            return True
        except Exception as exc:
            print(f"<< 写入失败: {exc}")
            return False

    return query, write


def query_float(query: Callable[[str], str | None], command: str) -> float | None:
    response = query(command)
    if response is None:
        return None
    try:
        return float(response)
    except ValueError:
        print(f"<< 不能转为数字: {response!r}")
        return None


def print_setpoint_check(
    name: str,
    target: float,
    actual: float | None,
    unit: str = "Hz",
    abs_tolerance: float | None = None,
) -> None:
    suffix = f" {unit}" if unit else ""
    print(f"{name}目标值: {target:.6f}{suffix}")
    if actual is None:
        print(f"{name}实际值: 读取失败")
        return
    print(f"{name}实际值: {actual:.6f}{suffix}")
    if abs_tolerance is None:
        abs_tolerance = 1.0 if unit == "Hz" else 1e-9
    if abs(actual - target) > max(abs(target) * 1e-6, abs_tolerance):
        print(f"提示: {name}设置后回读不一致，仪器可能拒绝该设置或需要其他模式。")


def print_actual_value(name: str, actual: float | None, unit: str = "") -> None:
    suffix = f" {unit}" if unit else ""
    if actual is None:
        print(f"{name}: 读取失败")
        return
    print(f"{name}: {actual:.6f}{suffix}")


def read_marker(query: Callable[[str], str | None], x_command: str, y_command: str, label: str) -> None:
    print_section(label)
    freq_hz = query_float(query, x_command)
    power_dbm = query_float(query, y_command)
    if freq_hz is not None:
        print(f"解析频率: {freq_hz / 1e9:.9f} GHz")
    if power_dbm is not None:
        print(f"解析功率: {power_dbm:.6f} dBm")
    if power_dbm == 0.0:
        print("提示: 这里读到 0 dBm，需结合屏幕 marker 和 SYST:ERR? 判断是否为真实读数。")


def drain_errors(query: Callable[[str], str | None], title: str) -> None:
    print_section(title)
    for _ in range(8):
        error = query("SYSTem:ERRor?")
        if error is None:
            return
        if error.startswith("0") or "No error" in error:
            return


def run_diagnostics() -> None:
    args = parse_args()
    if args.frequency_divisor <= 0:
        raise ValueError("--frequency-divisor must be positive")
    if args.sweep_points <= 0:
        raise ValueError("--sweep-points must be positive")
    if args.rbw_hz <= 0:
        raise ValueError("--rbw-hz must be positive")
    if args.vbw_hz <= 0:
        raise ValueError("--vbw-hz must be positive")

    try:
        import pyvisa
    except ImportError as exc:
        raise RuntimeError("当前环境缺少 pyvisa，请先在 thz504 环境安装 pyvisa。") from exc

    print_section("连接参数")
    print(f"address    : {args.address}")
    print(f"cal center GHz : {args.center_ghz}")
    print(f"cal span GHz   : {args.span_ghz}")
    print(f"divisor        : {args.frequency_divisor}")
    print(f"SA center GHz  : {args.center_ghz / args.frequency_divisor}")
    print(f"SA span GHz    : {args.span_ghz / args.frequency_divisor}")
    print(f"sweep points   : {args.sweep_points}")
    print("sweep time     : analyzer default (read back only)")
    print(f"RBW            : {args.rbw_hz} Hz")
    print(f"VBW            : {args.vbw_hz} Hz")
    print(f"timeout ms : {args.timeout_ms}")

    rm = None
    instrument = None
    try:
        rm, instrument, opened_address = open_instrument(pyvisa, args.address, args.timeout_ms)
        query, write = make_io(instrument)

        print_section("基础识别")
        query("*IDN?")
        query("*OPT?")
        drain_errors(query, "连接后错误队列")

        print_section("当前屏幕状态查询")
        query("SENSe:FREQuency:CENTer?")
        query("SENSe:FREQuency:SPAN?")
        query("SENSe:FREQuency:STARt?")
        query("SENSe:FREQuency:STOP?")
        query("SENSe:SWEep:POINts?")
        query("SENSe:SWEep:TIME?")
        query("SENSe:BANDwidth:RESolution?")
        query("SENSe:BANDwidth:VIDeo?")
        query("UNIT:POWer?")
        drain_errors(query, "状态查询后错误队列")

        print_section("测试 1: 不改频率，按当前屏幕寻峰")
        write("CALCulate:MARKer1:STATe ON")
        write("CALCulate:MARKer1:MAXimum")
        time.sleep(args.settle_s)
        read_marker(query, "CALCulate:MARKer1:X?", "CALCulate:MARKer1:Y?", "测试 1 结果")
        drain_errors(query, "测试 1 后错误队列")

        if not args.skip_configure:
            print_section("测试 2: 设置起止频率/点数/RBW/VBW后寻峰")
            settings = _mapped_sweep_settings(
                args.center_ghz,
                args.span_ghz,
                args.frequency_divisor,
                args.sweep_points,
                args.rbw_hz,
                args.vbw_hz,
            )
            for command in _sweep_settings_commands(settings):
                write(command)
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
            write("CALCulate:MARKer1:MAXimum")
            time.sleep(args.settle_s)
            read_marker(query, "CALCulate:MARKer1:X?", "CALCulate:MARKer1:Y?", "测试 2 结果")
            drain_errors(query, "测试 2 后错误队列")

            print_section("测试 3: 单次扫描完成后寻峰")
            write("INITiate:CONTinuous OFF")
            write("INITiate:IMMediate")
            query("*OPC?")
            write("CALCulate:MARKer1:MAXimum")
            time.sleep(args.settle_s)
            read_marker(query, "CALCulate:MARKer1:X?", "CALCulate:MARKer1:Y?", "测试 3 结果")
            drain_errors(query, "测试 3 后错误队列")

        print_section("测试 4: 常见简写命令兼容性")
        write("CALC:MARK ON")
        write("CALC:MARK:MAX")
        time.sleep(args.settle_s)
        read_marker(query, "CALC:MARK:X?", "CALC:MARK:Y?", "测试 4 结果")
        drain_errors(query, "测试 4 后错误队列")

        print_section("测试 5: 通道/窗口编号命令兼容性")
        write("CALC1:MARK1 ON")
        write("CALC1:MARK1:MAX")
        time.sleep(args.settle_s)
        read_marker(query, "CALC1:MARK1:X?", "CALC1:MARK1:Y?", "测试 5 结果")
        drain_errors(query, "测试 5 后错误队列")

        print_section("完成")
        print(f"实际打开资源名: {opened_address}")
        print("请把以上完整输出反馈回来，尤其是 *IDN?、SYST:ERR?、各测试的 X/Y 读数。")

    finally:
        if instrument is not None:
            instrument.close()
        if rm is not None:
            rm.close()


if __name__ == "__main__":
    run_diagnostics()
