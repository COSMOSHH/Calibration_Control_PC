from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class SignalGenerator(Protocol):
    """Minimal signal generator interface used by UI0 global confirmation."""

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def read_identity(self) -> str:
        ...

    def configure_cw(self, frequency_ghz: float, power_dbm: float, output_enabled: bool = True) -> None:
        ...


@dataclass
class SimulatedSignalGenerator:
    """In-memory signal source for tests and manual-control dry runs."""

    name: str
    address: str = "SIMULATED"
    connected: bool = False
    last_frequency_ghz: float | None = None
    last_power_dbm: float | None = None
    output_enabled: bool = False
    command_log: list[str] = field(default_factory=list)

    def connect(self) -> None:
        self.connected = True
        self.command_log.append("CONNECT")

    def disconnect(self) -> None:
        self.connected = False
        self.command_log.append("DISCONNECT")

    def is_connected(self) -> bool:
        return self.connected

    def read_identity(self) -> str:
        return f"SIMULATED,{self.name},0000,0.1"

    def configure_cw(self, frequency_ghz: float, power_dbm: float, output_enabled: bool = True) -> None:
        if not self.connected:
            raise RuntimeError(f"{self.name} signal generator is not connected")
        self.last_frequency_ghz = frequency_ghz
        self.last_power_dbm = power_dbm
        self.output_enabled = output_enabled
        self.command_log.extend(
            [
                f":FREQuency:FIXed {frequency_ghz:.12g}GHZ",
                f":POWer:LEVel {power_dbm:.6g}DBM",
                f":OUTPut:STATe {'ON' if output_enabled else 'OFF'}",
            ]
        )


class VisaSignalGenerator:
    """VISA/SCPI control for a Keysight-style CW signal generator."""

    def __init__(self, name: str, address: str, timeout_ms: int = 5000) -> None:
        self.name = name
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm = None
        self._instrument = None

    def connect(self) -> None:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required for VISA signal generator access") from exc

        self._rm = pyvisa.ResourceManager()
        self._instrument = self._rm.open_resource(self.address)
        self._instrument.timeout = self.timeout_ms

    def disconnect(self) -> None:
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None

    def is_connected(self) -> bool:
        return self._instrument is not None

    def read_identity(self) -> str:
        if self._instrument is None:
            raise RuntimeError(f"{self.name} signal generator is not connected")
        return self._instrument.query("*IDN?").strip()

    def configure_cw(self, frequency_ghz: float, power_dbm: float, output_enabled: bool = True) -> None:
        if self._instrument is None:
            raise RuntimeError(f"{self.name} signal generator is not connected")
        self._instrument.write(f":FREQuency:FIXed {frequency_ghz:.12g}GHZ")
        self._instrument.write(f":POWer:LEVel {power_dbm:.6g}DBM")
        self._instrument.write(f":OUTPut:STATe {'ON' if output_enabled else 'OFF'}")


class SignalSourceController:
    """Coordinates the LO and IF signal generators as one logical instrument pair."""

    def __init__(self, lo_source: SignalGenerator, if_source: SignalGenerator) -> None:
        self.lo_source = lo_source
        self.if_source = if_source

    def connect(self) -> None:
        self.lo_source.connect()
        try:
            self.if_source.connect()
        except Exception:
            self.lo_source.disconnect()
            raise

    def disconnect(self) -> None:
        errors: list[Exception] = []
        for source in (self.lo_source, self.if_source):
            try:
                source.disconnect()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    def configure_sources(
        self,
        lo_frequency_ghz: float,
        lo_power_dbm: float,
        if_frequency_ghz: float,
        if_power_dbm: float,
        output_enabled: bool = True,
    ) -> None:
        self.lo_source.configure_cw(lo_frequency_ghz, lo_power_dbm, output_enabled)
        self.if_source.configure_cw(if_frequency_ghz, if_power_dbm, output_enabled)

    def read_identities(self) -> tuple[str, str]:
        return self.lo_source.read_identity(), self.if_source.read_identity()
