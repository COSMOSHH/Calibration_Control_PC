from __future__ import annotations

import math
from statistics import mean


def dbm_to_uw(dbm: float) -> float:
    return 10 ** (dbm / 10.0) * 1000.0


def uw_to_dbm(uw: float) -> float:
    if uw <= 0:
        raise ValueError("uw must be positive")
    return 10.0 * math.log10(uw / 1000.0)


def average(values: list[float]) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    return mean(values)


def format_phase(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")

