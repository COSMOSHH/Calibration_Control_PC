from __future__ import annotations

import json
from enum import IntEnum
from typing import Iterable

from .models import FeedState


# 上位机到 STM32 的临时帧格式：
# AA | version | command | length_hi | length_lo | JSON payload | crc8 | BB
# CRC 的计算范围见 encode() 里的 body：不包含帧头 AA，包含 version/command/length/payload。
FRAME_HEAD = 0xAA
FRAME_TAIL = 0xBB
PROTOCOL_VERSION = 0x01


class CommandCode(IntEnum):
    """协议命令字。

    当前 UI 主要使用 SET_FEEDS；PING/SHUTDOWN_ALL 预留给后续联调或急停。
    """

    PING = 0x01
    SET_FEEDS = 0x10
    SHUTDOWN_ALL = 0x11


def crc8(data: bytes) -> int:
    """计算 CRC-8 校验值。

    多数串口下发问题可以从这里排查：
    - 先确认 STM32 端使用的多项式是否也是 0x07。
    - 再确认 STM32 端参与 CRC 的字节范围是否与 encode() 的 body 一致。
    """
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
    """临时上位机协议编码器。

    这里暂不编码 IPS-1924-6C / WQD0032H 的最终寄存器位，而是把 FeedState
    作为逻辑参数发给 STM32。固件协议冻结后，如需把 phase_deg 转芯片控制位，
    可以优先在这里或 STM32 端集中处理。
    """

    def encode(self, command: CommandCode, payload: dict) -> bytes:
        """把命令和 payload 打包为完整帧。"""
        # separators 去掉 JSON 里的多余空格，便于缩短串口帧长度。
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
        # STM32 端验 CRC 时应使用同样的 version/command/length/payload 字节序列。
        body = header[1:] + payload_bytes
        checksum = crc8(body)
        return header + payload_bytes + bytes([checksum, FRAME_TAIL])

    def encode_set_feeds(self, feeds: Iterable[FeedState]) -> bytes:
        """生成四馈源相位/使能状态下发帧。"""
        payload = {"feeds": [feed.as_payload() for feed in feeds]}
        return self.encode(CommandCode.SET_FEEDS, payload)

    def encode_shutdown_all(self) -> bytes:
        """生成全局关闭命令，当前 UI 尚未暴露独立按钮。"""
        return self.encode(CommandCode.SHUTDOWN_ALL, {"enabled": False})
