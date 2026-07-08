from __future__ import annotations

import time

from ..instruments.turntable import TurntableBase


class TurntableController:
    """把 UI 的单个目标角度作为 HOME 零点后的绝对角度下发。"""

    def __init__(self, driver: TurntableBase, settle_time_s: float = 0.12) -> None:
        self.driver = driver
        self.settle_time_s = settle_time_s
        self.current_angle = 0.0
        self._connected = False
        self._zeroed = False

    @property
    def is_simulated(self) -> bool:
        return bool(getattr(self.driver, "is_simulated", False))

    def connect(self, *, zero: bool = True) -> None:
        if not self._connected:
            self.driver.connect()
            self._connected = True
        if zero and not self._zeroed:
            self.set_zero()

    def disconnect(self) -> None:
        self.driver.close()
        self._connected = False
        self._zeroed = False
        self.current_angle = 0.0

    def is_connected(self) -> bool:
        return self._connected

    def set_zero(self) -> None:
        if not self._connected:
            self.driver.connect()
            self._connected = True
        self.driver.set_zero()
        self.current_angle = 0.0
        self._zeroed = True

    def move_to_angle(self, target_angle: float) -> float:
        """转到目标角度，返回本次实际转动的角度差。"""
        self.connect(zero=True)
        delta_angle = target_angle - self.current_angle
        if abs(delta_angle) <= 1e-9:
            return 0.0

        self.driver.trigger_absolute_move(target_angle)
        while self.driver.is_moving():
            time.sleep(0.02)
        if self.settle_time_s > 0:
            time.sleep(self.settle_time_s)

        self.current_angle = target_angle
        return delta_angle

    def emergency_stop(self) -> None:
        self.driver.emergency_stop()
