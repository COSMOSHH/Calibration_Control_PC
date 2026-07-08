from __future__ import annotations

from thz_calibration.controllers import TurntableController
from thz_calibration.instruments.turntable import TurntableBase


class RecordingTurntableDriver(TurntableBase):
    is_simulated = False

    def __init__(self) -> None:
        self.connected = False
        self.zero_count = 0
        self.absolute_targets: list[float] = []

    def connect(self) -> bool:
        self.connected = True
        return True

    def set_zero(self) -> None:
        self.zero_count += 1

    def trigger_absolute_move(self, target_angle: float) -> None:
        self.absolute_targets.append(target_angle)

    def is_moving(self) -> bool:
        return False

    def emergency_stop(self) -> None:
        pass


def test_move_to_angle_sends_absolute_targets_after_home() -> None:
    driver = RecordingTurntableDriver()
    controller = TurntableController(driver, settle_time_s=0)

    first_delta = controller.move_to_angle(20)
    second_delta = controller.move_to_angle(30)

    assert first_delta == 20
    assert second_delta == 10
    assert driver.zero_count == 1
    assert driver.absolute_targets == [20, 30]
    assert controller.current_angle == 30
