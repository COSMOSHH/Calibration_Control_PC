from __future__ import annotations

from typing import Iterable

from ..models import FeedState
from ..protocol import ProtocolEncoder
from ..transport.base import Transport, TransportResponse


class DeviceController:
    def __init__(self, transport: Transport, encoder: ProtocolEncoder | None = None) -> None:
        self.transport = transport
        self.encoder = encoder or ProtocolEncoder()

    def connect(self) -> None:
        self.transport.connect()

    def disconnect(self) -> None:
        self.transport.disconnect()

    def is_connected(self) -> bool:
        return self.transport.is_connected()

    def encode_feed_states(self, feed_states: Iterable[FeedState]) -> bytes:
        return self.encoder.encode_set_feeds(feed_states)

    def apply_feed_states(self, feed_states: Iterable[FeedState]) -> TransportResponse:
        frame = self.encode_feed_states(feed_states)
        return self.transport.send(frame)

    def shutdown_all(self) -> TransportResponse:
        return self.transport.send(self.encoder.encode_shutdown_all())
