from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from .config import DEFAULTS


@dataclass
class FeedState:
    """单个馈源下发给下位机前的逻辑状态。

    当前 STM32 payload 只使用 feed_id、phase_deg、enabled；amplitude 暂时保留
    在模型里，方便后续如果硬件协议增加幅度控制时不必重写上层流程。
    """

    feed_id: int
    phase_deg: float = 0.0
    amplitude: float = DEFAULTS.default_amplitude
    enabled: bool = True

    def as_payload(self) -> dict:
        """转成协议层 JSON payload 的单馈源字典。"""
        return {
            "feed_id": self.feed_id,
            "phase_deg": round(self.phase_deg, 6),
            "enabled": self.enabled,
        }


@dataclass
class ScanConfig:
    """UI0 扫描某一个目标馈源时使用的完整配置。

    target_feed_id 指当前正在扫描相位的馈源；前序馈源的最佳相位由 UI 层
    组装成 feed_states 后交给 CalibrationEngine。
    """

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
        """在真正扫描前做参数校验，避免硬件已经开始动作才发现输入不合法。"""
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
        """生成扫描相位点列表。

        使用 Decimal 而不是 float 直接累加，避免 5.625 这类小数步进时
        因二进制浮点误差漏掉最后一个点。
        """
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
    """一次频谱仪读数时的上下文。

    模拟频谱仪会根据这里的频点、波束角、目标馈源和相位生成假数据；
    真实频谱仪当前主要使用 visa_address，保留这些字段用于日志和后续扩展。
    """

    frequency_ghz: float
    beam_angle_deg: float
    target_feed_id: int
    phase_deg: float
    feed_states: list[FeedState] = field(default_factory=list)


@dataclass
class ScanPoint:
    """UI0 扫描得到的单个相位点结果。"""

    index: int
    total: int
    target_feed_id: int
    phase_deg: float
    average_power_dbm: float
    average_power_uw: float
    samples_dbm: list[float]
    timestamp: datetime = field(default_factory=datetime.now)

    def as_row(self) -> dict:
        """转成 Excel 导出层可以直接写入的一行数据。"""
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
    """一个目标馈源扫描完成后的结果集合。"""

    config: ScanConfig
    points: list[ScanPoint]

    @property
    def best_point(self) -> ScanPoint | None:
        """功率最大的点即当前扫描的最佳相位点。"""
        if not self.points:
            return None
        return max(self.points, key=lambda point: point.average_power_uw)


def default_feed_states(enabled_feeds: Iterable[int] | None = None) -> list[FeedState]:
    """按 enabled_feeds 快速生成四个馈源的默认状态。

    UI0 扫描会逐步打开 Feed1、Feed2、Feed3、Feed4；这个辅助函数用于
    快速得到“哪些 CE 打开、哪些 CE 关闭”的初始列表。
    """
    enabled = set(range(1, DEFAULTS.feed_count + 1)) if enabled_feeds is None else set(enabled_feeds)
    return [
        FeedState(feed_id=feed_id, enabled=feed_id in enabled)
        for feed_id in range(1, DEFAULTS.feed_count + 1)
    ]
