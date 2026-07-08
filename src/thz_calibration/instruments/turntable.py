from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Any


class TurntableBase(ABC):
    """模拟转台和真实转台的统一接口。"""

    @abstractmethod
    def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_zero(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def trigger_absolute_move(self, target_angle: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_moving(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def emergency_stop(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """关闭底层连接；模拟转台无资源可释放。"""


class SimulatedTurntableDriver(TurntableBase):
    """无硬件调试用模拟转台。"""

    is_simulated = True

    def __init__(self, move_time_s: float = 0.08) -> None:
        self.connected = False
        self.current_angle = 0.0
        self._moving_until = 0.0
        self._move_time_s = move_time_s
        self._stopped = False

    def connect(self) -> bool:
        self.connected = True
        self._stopped = False
        return self.connected

    def set_zero(self) -> None:
        self._ensure_connected()
        self.current_angle = 0.0

    def trigger_absolute_move(self, target_angle: float) -> None:
        self._ensure_connected()
        if self._stopped:
            raise RuntimeError("模拟转台已急停，不能继续运动。")
        self.current_angle = target_angle
        self._moving_until = time.monotonic() + self._move_time_s

    def is_moving(self) -> bool:
        return time.monotonic() < self._moving_until and not self._stopped

    def emergency_stop(self) -> None:
        self._stopped = True
        self._moving_until = 0.0

    def close(self) -> None:
        self.connected = False

    def _ensure_connected(self) -> None:
        if not self.connected:
            raise RuntimeError("模拟转台尚未连接。")


@dataclass(frozen=True)
class GcdRegisterMap:
    """GCD-030401M 控制器用到的寄存器和命令。"""

    status_register: int = 0x0F00
    trigger_register: int = 0x6002
    path0_base_register: int = 0x6200
    set_zero_command: int = 0x0021
    start_path0_command: int = 0x0010
    emergency_stop_command: int = 0x0040
    running_status_mask: int = 0x0004


class GcdTurntableDriver(TurntableBase):
    """GCD-030401M 单轴控制器的 Modbus RTU 驱动。

    路径 0 的位置参数按 HOME/设零后的绝对位置理解：上层传入目标角度，
    本类换算成绝对脉冲位置，写入路径 0 参数寄存器，再触发路径 0 运行。
    """

    is_simulated = False

    def __init__(
        self,
        port: str,
        baudrate: int = 38400,
        slave_id: int = 1,
        *,
        pulses_per_degree: float = 2000.0,
        move_timeout_s: float = 30.0,
        poll_interval_s: float = 0.05,
        path_mode: int = 0x0001,
        speed: int = 2000,
        acceleration: int = 1000,
        deceleration: int = 1000,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.pulses_per_degree = pulses_per_degree
        self.move_timeout_s = move_timeout_s
        self.poll_interval_s = poll_interval_s
        self.path_mode = path_mode
        self.speed = speed
        self.acceleration = acceleration
        self.deceleration = deceleration
        self.registers = GcdRegisterMap()
        self.connected = False
        self.current_angle = 0.0
        self._client: Any | None = None
        self._stopped = False
        self._move_started_at: float | None = None

    def connect(self) -> bool:
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError as exc:
            raise RuntimeError("未安装 pymodbus，请先执行 pip install -r requirements.txt。") from exc

        self._client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=1.0,
        )
        self.connected = bool(self._client.connect())
        if not self.connected:
            raise RuntimeError(f"无法连接真实转台串口：{self.port}。")
        self._stopped = False
        return self.connected

    def set_zero(self) -> None:
        self._ensure_connected()
        self._write_register(self.registers.trigger_register, self.registers.set_zero_command)
        self.current_angle = 0.0

    def trigger_absolute_move(self, target_angle: float) -> None:
        self._ensure_connected()
        if self._stopped:
            raise RuntimeError("真实转台已急停，不能继续下发运动指令。")

        pulses = self._degrees_to_pulses(target_angle)
        high_word, low_word = self._split_signed_32bit(pulses)
        path_values = [
            self.path_mode,
            high_word,
            low_word,
            self._to_u16(self.speed),
            self._to_u16(self.acceleration),
            self._to_u16(self.deceleration),
            0x0000,
        ]
        self._write_registers(self.registers.path0_base_register, path_values)
        self._write_register(self.registers.trigger_register, self.registers.start_path0_command)
        self.current_angle = target_angle
        self._move_started_at = time.monotonic()

    def is_moving(self) -> bool:
        self._ensure_connected()
        if self._move_started_at is not None:
            elapsed = time.monotonic() - self._move_started_at
            if elapsed > self.move_timeout_s:
                self.emergency_stop()
                raise RuntimeError(f"真实转台运动超时，已急停。超时时间：{self.move_timeout_s:.1f}s。")

        status = self.read_status()
        moving = (status & self.registers.running_status_mask) != 0
        if not moving:
            self._move_started_at = None
        return moving

    def emergency_stop(self) -> None:
        self._ensure_connected()
        self._stopped = True
        self._move_started_at = None
        self._write_register(self.registers.trigger_register, self.registers.emergency_stop_command)

    def read_status(self) -> int:
        self._ensure_connected()
        response = self._read_holding_registers(self.registers.status_register, count=1)
        self._raise_for_modbus_error(response, f"读取状态寄存器 0x{self.registers.status_register:04X} 失败")
        return int(response.registers[0])

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self.connected = False
        self._client = None

    def _degrees_to_pulses(self, angle: float) -> int:
        return int(round(angle * self.pulses_per_degree))

    def _write_register(self, address: int, value: int) -> None:
        response = self._call_modbus(
            "write_register",
            address,
            self._to_u16(value),
        )
        self._raise_for_modbus_error(response, f"写寄存器 0x{address:04X} 失败")

    def _write_registers(self, address: int, values: list[int]) -> None:
        response = self._call_modbus(
            "write_registers",
            address,
            [self._to_u16(value) for value in values],
        )
        self._raise_for_modbus_error(response, f"写寄存器 0x{address:04X} 起始的连续寄存器失败")

    def _read_holding_registers(self, address: int, *, count: int) -> Any:
        return self._call_modbus("read_holding_registers", address, count=count)

    def _call_modbus(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self._client, method_name)
        try:
            return method(*args, **kwargs, device_id=self.slave_id)
        except TypeError:
            return method(*args, **kwargs, slave=self.slave_id)

    def _raise_for_modbus_error(self, response: Any, message: str) -> None:
        if response is None or response.isError():
            raise RuntimeError(f"{message}，请检查串口、从站地址、接线和设备供电。")

    def _ensure_connected(self) -> None:
        if not self.connected or self._client is None:
            raise RuntimeError("真实转台尚未连接。")

    @staticmethod
    def _split_signed_32bit(value: int) -> tuple[int, int]:
        value &= 0xFFFFFFFF
        return (value >> 16) & 0xFFFF, value & 0xFFFF

    @staticmethod
    def _to_u16(value: int) -> int:
        return value & 0xFFFF
