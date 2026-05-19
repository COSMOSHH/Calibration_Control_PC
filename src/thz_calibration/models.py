from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from .config import DEFAULTS


@dataclass
class FeedState:
    feed_id: int
    phase_deg: float = 0.0
    amplitude: float = DEFAULTS.default_amplitude
    enabled: bool = True

    def as_payload(self) -> dict:
        return {
            "feed_id": self.feed_id,
            "phase_deg": round(self.phase_deg, 6),
            "enabled": self.enabled,
        }


@dataclass
class ScanConfig:
    target_feed_id: int = 2
    frequency_ghz: float = DEFAULTS.frequency_ghz
    beam_angle_deg: float = DEFAULTS.beam_angle_deg
    phase_start_deg: float = DEFAULTS.phase_start_deg
    phase_end_deg: float = DEFAULTS.phase_end_deg
    phase_step_deg: float = DEFAULTS.phase_step_deg
    amplitude: float = DEFAULTS.default_amplitude
    settle_time_ms: int = DEFAULTS.settle_time_ms
    sample_count: int = DEFAULTS.sample_count

    def validate(self) -> None:
        if not 1 <= self.target_feed_id <= DEFAULTS.feed_count:
            raise ValueError("target_feed_id must be between 1 and 4")
        if self.phase_step_deg <= 0:
            raise ValueError("phase_step_deg must be positive")
        if self.phase_end_deg < self.phase_start_deg:
            raise ValueError("phase_end_deg must be greater than or equal to phase_start_deg")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.settle_time_ms < 0:
            raise ValueError("settle_time_ms must be non-negative")

    def phase_points(self) -> list[float]:
        self.validate()
        start = Decimal(str(self.phase_start_deg))
        end = Decimal(str(self.phase_end_deg))
        step = Decimal(str(self.phase_step_deg))
        epsilon = Decimal("0.0000001")

        points: list[float] = []
        current = start
        while current <= end + epsilon:
            points.append(float(current))
            current += step
        return points


@dataclass
class MeasurementContext:
    frequency_ghz: float
    beam_angle_deg: float
    target_feed_id: int
    phase_deg: float
    feed_states: list[FeedState] = field(default_factory=list)


@dataclass
class ScanPoint:
    index: int
    total: int
    target_feed_id: int
    phase_deg: float
    average_power_dbm: float
    average_power_uw: float
    samples_dbm: list[float]
    timestamp: datetime = field(default_factory=datetime.now)

    def as_row(self) -> dict:
        return {
            "index": self.index,
            "total": self.total,
            "target_feed_id": self.target_feed_id,
            "phase_deg": self.phase_deg,
            "average_power_dbm": self.average_power_dbm,
            "average_power_uw": self.average_power_uw,
            "samples_dbm": ", ".join(f"{sample:.3f}" for sample in self.samples_dbm),
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }


@dataclass
class CalibrationResult:
    config: ScanConfig
    points: list[ScanPoint]

    @property
    def best_point(self) -> ScanPoint | None:
        if not self.points:
            return None
        return max(self.points, key=lambda point: point.average_power_uw)


def default_feed_states(enabled_feeds: Iterable[int] | None = None) -> list[FeedState]:
    enabled = set(enabled_feeds or range(1, DEFAULTS.feed_count + 1))
    return [
        FeedState(feed_id=feed_id, enabled=feed_id in enabled)
        for feed_id in range(1, DEFAULTS.feed_count + 1)
    ]
