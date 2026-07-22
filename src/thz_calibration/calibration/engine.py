from __future__ import annotations

import time
from copy import deepcopy
from typing import Callable

from ..controllers import DeviceController
from ..instruments import SpectrumAnalyzer
from ..models import CalibrationResult, FeedState, MeasurementContext, ScanConfig, ScanPoint
from ..utils import dbm_to_uw


PointCallback = Callable[[ScanPoint], None]
LogCallback = Callable[[str], None]
StopCallback = Callable[[], bool]


class CalibrationEngine:
    """UI0 的校准扫描核心流程。

    这个类不直接操作界面，也不直接保存 Excel；它只负责按 ScanConfig 逐点下发
    相位、等待硬件稳定、读取频谱仪功率，并把 ScanPoint 通过回调交给 UI。
    """

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
        """扫描一个目标馈源的相位范围。

        feed_states 是 UI 层准备好的当前四馈源状态：前序馈源通常保持最佳相位，
        当前 target_feed_id 会在循环里不断替换 phase_deg。
        """
        config.validate()
        self.analyzer.configure_average_count(config.sample_count)
        phase_points = config.phase_points()
        points: list[ScanPoint] = []

        for index, phase in enumerate(phase_points, start=1):
            # UI 可以通过 should_stop 请求中断；中断后返回已采集到的点。
            if should_stop and should_stop():
                if on_log:
                    on_log("扫描已停止")
                break

            # 每个相位点都复制一份 feed_states，避免修改 UI 保存的基准状态。
            current_states = self._prepare_states(feed_states, config.target_feed_id, phase, config.amplitude)
            response = self.device.apply_feed_states(current_states)
            if not response.ok:
                raise RuntimeError(f"下位机发送失败: {response.message}")

            # 终端日志用于联调确认“本次实际下发了哪些 CE/相位”。
            print(self._format_feed_phase_log(current_states), flush=True)
            if on_log:
                on_log(f"Feed{config.target_feed_id} 相位 {phase:g} deg 已下发，等待 {config.settle_time_ms} ms")
            time.sleep(config.settle_time_ms / 1000.0)

            # context 同时服务真实读数日志和模拟频谱仪生成曲线。
            context = MeasurementContext(
                frequency_ghz=config.frequency_ghz,
                beam_angle_deg=config.beam_angle_deg,
                target_feed_id=config.target_feed_id,
                phase_deg=phase,
                feed_states=current_states,
            )
            avg_dbm = self.analyzer.read_peak_power_dbm(context)
            samples = [avg_dbm]
            # ScanPoint 里同时保存 dBm 和 uW；Excel 目前写 uW。
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
                # UI0 通过回调刷新进度/日志，Engine 不直接依赖具体控件。
                on_point(point)

        return CalibrationResult(config=config, points=points)

    def _prepare_states(
        self,
        feed_states: list[FeedState],
        target_feed_id: int,
        phase_deg: float,
        amplitude: float,
    ) -> list[FeedState]:
        """生成当前相位点要下发的四馈源状态。

        只替换目标馈源的 phase/amplitude/enabled；其他馈源保持 UI 层传入状态。
        """
        states = deepcopy(feed_states)
        for state in states:
            if state.feed_id == target_feed_id:
                state.phase_deg = phase_deg
                state.amplitude = amplitude
                state.enabled = True
        return states

    def _format_feed_phase_log(self, feed_states: list[FeedState]) -> str:
        """格式化终端联调日志，显示 CE 开关和每个 Feed 的相位。"""
        states = ", ".join(
            f"CE{state.feed_id}={'打开' if state.enabled else '关闭'} "
            f"Feed{state.feed_id}={state.phase_deg:.6f} deg"
            for state in sorted(feed_states, key=lambda item: item.feed_id)
        )
        return f"校准发送状态：{states}"
