from __future__ import annotations

from .base import TransportResponse


class SimulatedTransport:
    def __init__(self) -> None:
        self._connected = False
        self.last_frame: bytes = b""

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def send(self, frame: bytes) -> TransportResponse:
        if not self._connected:
            return TransportResponse(ok=False, message="simulated transport is not connected")
        self.last_frame = frame
        return TransportResponse(ok=True, raw=b"SIM_ACK", message="simulated ACK")

