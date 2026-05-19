from __future__ import annotations

from .base import TransportResponse


class SerialTransport:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 0.5) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None

    def connect(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("pyserial is required for serial transport") from exc

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self.timeout,
        )
        self._serial.setDTR(False)
        self._serial.setRTS(False)

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()

    def is_connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def send(self, frame: bytes) -> TransportResponse:
        if not self.is_connected():
            return TransportResponse(ok=False, message="serial transport is not connected")

        try:
            self._serial.write(frame)
            response = self._serial.readline()
            return TransportResponse(ok=True, raw=response, message=response.hex() if response else "sent")
        except Exception as exc:
            return TransportResponse(ok=False, message=str(exc))

