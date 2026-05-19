from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TransportResponse:
    ok: bool
    raw: bytes = b""
    message: str = ""


class Transport(Protocol):
    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def send(self, frame: bytes) -> TransportResponse:
        ...

