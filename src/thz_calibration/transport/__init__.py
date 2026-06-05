# 传输包同时暴露真实串口和模拟传输，配置层按运行模式选择具体实现。
from .base import Transport, TransportResponse
from .serial_transport import SerialTransport
from .simulated import SimulatedTransport

__all__ = ["Transport", "TransportResponse", "SerialTransport", "SimulatedTransport"]
