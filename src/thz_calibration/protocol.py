from __future__ import annotations

import json
from enum import IntEnum
from typing import Iterable

from .models import FeedState


FRAME_HEAD = 0xAA
FRAME_TAIL = 0xBB
PROTOCOL_VERSION = 0x01


class CommandCode(IntEnum):
    PING = 0x01
    SET_FEEDS = 0x10
    SHUTDOWN_ALL = 0x11


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


class ProtocolEncoder:
    """Temporary upper-computer frame.

    The old scheme used AA + payload + CRC8 + BB framing. The STM32-side
    register layout is intentionally not encoded here yet; payloads carry
    feed-level logical parameters until the final firmware protocol is frozen.
    """

    def encode(self, command: CommandCode, payload: dict) -> bytes:
        payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        length = len(payload_bytes)
        if length > 65535:
            raise ValueError("payload is too large")

        header = bytes([
            FRAME_HEAD,
            PROTOCOL_VERSION,
            int(command),
            (length >> 8) & 0xFF,
            length & 0xFF,
        ])
        body = header[1:] + payload_bytes
        checksum = crc8(body)
        return header + payload_bytes + bytes([checksum, FRAME_TAIL])

    def encode_set_feeds(self, feeds: Iterable[FeedState]) -> bytes:
        payload = {"feeds": [feed.as_payload() for feed in feeds]}
        return self.encode(CommandCode.SET_FEEDS, payload)

    def encode_shutdown_all(self) -> bytes:
        return self.encode(CommandCode.SHUTDOWN_ALL, {"enabled": False})

