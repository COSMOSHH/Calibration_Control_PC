from __future__ import annotations

from .base import TransportResponse


class SimulatedTransport:
    """无硬件调试用的传输实现。

    它会保存最近一次发送的完整帧，并返回固定 ACK。这样 UI/协议/校准流程
    可以在没有 STM32 的情况下跑通，调试时也能在 UI1 的反馈窗查看 HEX。
    """

    def __init__(self) -> None:
        self._connected = False
        # last_frame 方便测试或调试时确认上层生成的最终串口帧。
        self.last_frame: bytes = b""

    def connect(self) -> None:
        """模拟连接成功。"""
        self._connected = True

    def disconnect(self) -> None:
        """模拟断开连接。"""
        self._connected = False

    def is_connected(self) -> bool:
        """返回模拟连接状态。"""
        return self._connected

    def send(self, frame: bytes) -> TransportResponse:
        """记录帧并返回模拟 ACK。"""
        if not self._connected:
            return TransportResponse(ok=False, message="simulated transport is not connected")
        self.last_frame = frame
        return TransportResponse(ok=True, raw=b"SIM_ACK", message="simulated ACK")
