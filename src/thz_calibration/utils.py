from __future__ import annotations

import math
from statistics import mean


def dbm_to_uw(dbm: float) -> float:
    """把频谱仪常见的 dBm 单位转换为 uW。

    Excel 保存和 UI 展示使用 uW，更直观；频谱仪/模拟器内部仍以 dBm 读数为主。
    """
    return 10 ** (dbm / 10.0) * 1000.0


def uw_to_dbm(uw: float) -> float:
    """把 uW 转回 dBm，主要用于测试或后续反算。"""
    if uw <= 0:
        raise ValueError("uw must be positive")
    return 10.0 * math.log10(uw / 1000.0)


def average(values: list[float]) -> float:
    """统一的平均值入口，空列表直接报错，避免扫描结果静默写出 NaN。"""
    if not values:
        raise ValueError("values cannot be empty")
    return mean(values)


def format_phase(value: float) -> str:
    """格式化相位数字，用于文件名/日志，避免 30.000000 这类冗余字符串。"""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")
