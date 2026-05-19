from __future__ import annotations

import time
from copy import deepcopy
from typing import Callable

from ..controllers import DeviceController
from ..instruments import SpectrumAnalyzer
from ..models import CalibrationResult, FeedState, MeasurementContext, ScanConfig, ScanPoint
from ..utils import average, dbm_to_uw


PointCallback = Callable[[ScanPoint], None]
LogCallback = Callable[[str], None]
StopCallback = Callable[[], bool]


class CalibrationEngine:
    def __init__(self, device: DeviceController, analyzer: SpectrumAnalyzer) -> None:
        self.device = device
        self.analyzer = analyzer

    def scan_feed(
        self,
        config: ScanConfig,
        feed_states: list[FeedState],
        on_point: PointCallback | None = None,
        on_log: LogCallback | None = None,
        should_stop: StopCallback | None = None,
    ) -> CalibrationResult:
        config.validate()
        phase_points = config.phase_points()
        points: list[ScanPoint] = []

        for index, phase in enumerate(phase_points, start=1):
            if should_stop and should_stop():
                if on_log:
                    on_log("扫描已停止")
                break

            current_states = self._prepare_states(feed_states, config.target_feed_id, phase, config.amplitude)
            response = self.device.apply_feed_states(current_states)
            if not response.ok:
                raise RuntimeError(f"下位机发送失败: {response.message}")

            print(self._format_feed_phase_log(current_states), flush=True)
            if on_log:
                on_log(f"Feed{config.target_feed_id} 相位 {phase:g} deg 已下发，等待 {config.settle_time_ms} ms")
            time.sleep(config.settle_time_ms / 1000.0)

            context = MeasurementContext(
                frequency_ghz=config.frequency_ghz,
                beam_angle_deg=config.beam_angle_deg,
                target_feed_id=config.target_feed_id,
                phase_deg=phase,
                feed_states=current_states,
            )
            samples = self._sample_power_dbm(context, config.sample_count)
            avg_dbm = average(samples)
            point = ScanPoint(
                index=index,
                total=len(phase_points),
                target_feed_id=config.target_feed_id,
                phase_deg=phase,
                average_power_dbm=avg_dbm,
                average_power_uw=dbm_to_uw(avg_dbm),
                samples_dbm=samples,
            )
            points.append(point)

            if on_point:
                on_point(point)

        return CalibrationResult(config=config, points=points)

    def _sample_power_dbm(self, context: MeasurementContext, sample_count: int) -> list[float]:
        samples: list[float] = []
        for sample_index in range(sample_count):
            samples.append(self.analyzer.read_peak_power_dbm(context))
            if sample_index < sample_count - 1:
                time.sleep(0.05)
        return samples

    def _prepare_states(
        self,
        feed_states: list[FeedState],
        target_feed_id: int,
        phase_deg: float,
        amplitude: float,
    ) -> list[FeedState]:
        states = deepcopy(feed_states)
        for state in states:
            if state.feed_id == target_feed_id:
                state.phase_deg = phase_deg
                state.amplitude = amplitude
                state.enabled = True
        return states

    def _format_feed_phase_log(self, feed_states: list[FeedState]) -> str:
        states = ", ".join(
            f"CE{state.feed_id}={'打开' if state.enabled else '关闭'} "
            f"Feed{state.feed_id}={state.phase_deg:.6f} deg"
            for state in sorted(feed_states, key=lambda item: item.feed_id)
        )
        return f"校准发送状态：{states}"
