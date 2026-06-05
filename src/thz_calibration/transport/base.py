from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TransportResponse:
    """传输层统一返回值。

    ok 表示发送流程是否成功；raw 保存下位机原始返回字节；message 用于 UI 展示。
    """

    ok: bool
    raw: bytes = b""
    message: str = ""


class Transport(Protocol):
    """所有传输实现必须满足的接口。

    DeviceController 只依赖这个协议，因此可以在 SerialTransport 和
    SimulatedTransport 之间切换，不影响 UI/校准引擎。
    """

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def send(self, frame: bytes) -> TransportResponse:
        ...
