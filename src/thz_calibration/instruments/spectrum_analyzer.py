from __future__ import annotations

import math
import random
import time
from typing import Protocol

from ..models import MeasurementContext
from ..utils import dbm_to_uw, uw_to_dbm


class SpectrumAnalyzer(Protocol):
    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def read_identity(self) -> str:
        ...

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        ...


class SimulatedSpectrumAnalyzer:
    def __init__(self, address: str = "SIMULATED") -> None:
        self.address = address
        self._connected = False
        self._rng = random.Random(504)

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def read_identity(self) -> str:
        return "SIMULATED,THZ-SPECTRUM,0000,0.1"

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        if not self._connected:
            raise RuntimeError("simulated spectrum analyzer is not connected")

        if context is None:
            return -20.0 + self._rng.uniform(-0.2, 0.2)

        ideal_phase = {
            1: 0.0,
            2: 112.5,
            3: 202.5,
            4: 281.25,
        }.get(context.target_feed_id, 0.0)
        delta_rad = math.radians((context.phase_deg - ideal_phase) % 360.0)
        coherence = (1.0 + math.cos(delta_rad)) / 2.0
        active_count = sum(1 for feed in context.feed_states if feed.enabled)
        baseline_uw = 16.0 * max(active_count, 1)
        power_uw = baseline_uw * (0.35 + 0.65 * coherence)
        noise_uw = self._rng.uniform(-0.35, 0.35)
        return uw_to_dbm(max(power_uw + noise_uw, 0.001))


class VisaSpectrumAnalyzer:
    def __init__(self, address: str, timeout_ms: int = 5000) -> None:
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm = None
        self._instrument = None

    def connect(self) -> None:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required for VISA spectrum analyzer access") from exc

        self._rm = pyvisa.ResourceManager()
        self._instrument = self._rm.open_resource(self.address)
        self._instrument.timeout = self.timeout_ms

    def disconnect(self) -> None:
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None

    def is_connected(self) -> bool:
        return self._instrument is not None

    def read_identity(self) -> str:
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
        return self._instrument.query("*IDN?").strip()

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        if self._instrument is None:
            raise RuntimeError("VISA instrument is not connected")
        self._instrument.write("CALCulate:MARKer1:MAXimum")
        time.sleep(0.1)
        return float(self._instrument.query("CALCulate:MARKer1:Y?"))

