from __future__ import annotations

from thz_calibration.calibration.engine import CalibrationEngine
from thz_calibration.models import FeedState, MeasurementContext, ScanConfig, default_feed_states
from thz_calibration.transport.base import TransportResponse


class FakeDevice:
    def __init__(self) -> None:
        self.sent_states: list[list[FeedState]] = []

    def apply_feed_states(self, feed_states: list[FeedState]) -> TransportResponse:
        self.sent_states.append(list(feed_states))
        return TransportResponse(ok=True, message="OK")


class CountingAnalyzer:
    def __init__(self) -> None:
        self.average_counts: list[int] = []
        self.read_contexts: list[MeasurementContext | None] = []

    def configure_average_count(self, count: int) -> None:
        self.average_counts.append(count)

    def read_peak_power_dbm(self, context: MeasurementContext | None = None) -> float:
        self.read_contexts.append(context)
        return -12.5


def test_scan_feed_uses_sample_count_as_hardware_average_count() -> None:
    device = FakeDevice()
    analyzer = CountingAnalyzer()
    engine = CalibrationEngine(device, analyzer)  # type: ignore[arg-type]
    config = ScanConfig(
        target_feed_id=2,
        phase_start_deg=0.0,
        phase_end_deg=5.625,
        phase_step_deg=5.625,
        settle_time_ms=0,
        sample_count=3,
    )

    result = engine.scan_feed(config, default_feed_states())

    assert analyzer.average_counts == [3]
    assert len(analyzer.read_contexts) == 2
    assert [context.phase_deg for context in analyzer.read_contexts if context is not None] == [0.0, 5.625]
    assert [point.samples_dbm for point in result.points] == [[-12.5], [-12.5]]
    assert [point.average_power_dbm for point in result.points] == [-12.5, -12.5]
