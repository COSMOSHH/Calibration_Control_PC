from __future__ import annotations

from .base import TransportResponse


class SerialTransport:
    """真实 STM32 串口传输实现。

    这里不关心 payload 内容，只负责打开串口、写入完整帧、读取一行响应。
    如果 UI 显示 HEX 正确但下位机无反应，优先检查本类的端口、波特率和 ACK 读取方式。
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 0.5) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None

    def connect(self) -> None:
        """打开串口连接。

        DTR/RTS 关闭是为了避免某些 USB-串口模块在打开端口时触发下位机复位。
        """
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
        """关闭串口，窗口退出或切换连接时调用。"""
        if self._serial and self._serial.is_open:
            self._serial.close()

    def is_connected(self) -> bool:
        """判断当前串口对象是否存在并处于打开状态。"""
        return bool(self._serial and self._serial.is_open)

    def send(self, frame: bytes) -> TransportResponse:
        """发送完整协议帧并读取一行下位机返回。

        当前 STM32 返回格式未强约束，所以 response 只作为 raw/message 回传给 UI。
        如果固件改成固定 ACK/NACK，可以在这里解析并设置 ok。
        """
        if not self.is_connected():
            return TransportResponse(ok=False, message="serial transport is not connected")

        try:
            self._serial.write(frame)
            response = self._serial.readline()
            return TransportResponse(ok=True, raw=response, message=response.hex() if response else "sent")
        except Exception as exc:
            return TransportResponse(ok=False, message=str(exc))
