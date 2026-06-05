from __future__ import annotations

from typing import Iterable

from ..models import FeedState
from ..protocol import ProtocolEncoder
from ..transport.base import Transport, TransportResponse


class DeviceController:
    """设备控制入口：把上层 FeedState 转成协议帧并交给传输层。

    调试下发链路时建议按这个顺序看：
    UI/Engine 组装 FeedState -> encode_feed_states 生成 HEX -> transport.send 实际发送。
    """

    def __init__(self, transport: Transport, encoder: ProtocolEncoder | None = None) -> None:
        self.transport = transport
        self.encoder = encoder or ProtocolEncoder()

    def connect(self) -> None:
        """连接底层传输，串口模式会在这里打开 COM 口。"""
        self.transport.connect()

    def disconnect(self) -> None:
        """断开底层传输。"""
        self.transport.disconnect()

    def is_connected(self) -> bool:
        """查询传输层连接状态，用于 UI 按钮状态或调试确认。"""
        return self.transport.is_connected()

    def encode_feed_states(self, feed_states: Iterable[FeedState]) -> bytes:
        """只编码不发送，UI1 用它在信息反馈窗打印完整 HEX。"""
        return self.encoder.encode_set_feeds(feed_states)

    def apply_feed_states(self, feed_states: Iterable[FeedState]) -> TransportResponse:
        """编码并发送四馈源状态，是 UI0 扫描和 UI1 数据发送的共同出口。"""
        frame = self.encode_feed_states(feed_states)
        return self.transport.send(frame)

    def shutdown_all(self) -> TransportResponse:
        """发送全局关闭命令，预留给后续急停/关闭输出功能。"""
        return self.transport.send(self.encoder.encode_shutdown_all())
