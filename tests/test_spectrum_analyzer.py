import sys
from types import SimpleNamespace

import pytest

from thz_calibration.instruments import spectrum_analyzer
from thz_calibration.instruments.spectrum_analyzer import VisaSpectrumAnalyzer, XianGpibSpectrumAnalyzer
from thz_calibration.models import MeasurementContext


class FakeVisaInstrument:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.queries: list[str] = []

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command == "*OPC?":
            return "1"
        return "-12.5"


class FailingResourceManager:
    def __init__(self) -> None:
        self.closed = False
        self.opened: list[str] = []

    def open_resource(self, address: str):
        self.opened.append(address)
        raise RuntimeError(f"missing resource: {address}")

    def list_resources(self) -> tuple[str, ...]:
        return ("TCPIP0::10.18.18.4::inst0::INSTR",)

    def close(self) -> None:
        self.closed = True


class FallbackResourceManager:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def open_resource(self, address: str):
        self.opened.append(address)
        if address == "TCPIP0::10.18.18.4::inst0::INSTR":
            return FakeVisaInstrument()
        raise RuntimeError(f"missing resource: {address}")


class ProtocolFallbackResourceManager:
    def __init__(self, target: str) -> None:
        self.target = target
        self.opened: list[str] = []
        self.instrument = FakeVisaInstrument()

    def open_resource(self, address: str):
        self.opened.append(address)
        if address == self.target:
            return self.instrument
        raise RuntimeError(f"missing resource: {address}")


def make_context(frequency_ghz: float = 212.0) -> MeasurementContext:
    return MeasurementContext(
        frequency_ghz=frequency_ghz,
        beam_angle_deg=30.0,
        target_feed_id=2,
        phase_deg=45.0,
    )


def test_visa_analyzer_sets_sweep_range_before_marker_read(monkeypatch) -> None:
    monkeypatch.setattr(spectrum_analyzer.time, "sleep", lambda _: None)
    instrument = FakeVisaInstrument()
    analyzer = VisaSpectrumAnalyzer("SIM", sweep_span_ghz=0.25)
    analyzer._instrument = instrument

    power_dbm = analyzer.read_peak_power_dbm(make_context())

    assert power_dbm == -12.5
    assert instrument.writes == [
        "SENSe:FREQuency:CENTer 212000000000",
        "SENSe:FREQuency:SPAN 250000000",
        "CALCulate:MARKer1:MAXimum",
    ]
    assert instrument.queries == ["CALCulate:MARKer1:Y?"]


def test_visa_analyzer_maps_calibration_frequency_with_divisor(monkeypatch) -> None:
    monkeypatch.setattr(spectrum_analyzer.time, "sleep", lambda _: None)
    instrument = FakeVisaInstrument()
    analyzer = VisaSpectrumAnalyzer("SIM", sweep_span_ghz=1.0, frequency_divisor=10.0)
    analyzer._instrument = instrument

    analyzer.read_peak_power_dbm(make_context(215.0))

    assert instrument.writes == [
        "SENSe:FREQuency:CENTer 21500000000",
        "SENSe:FREQuency:SPAN 100000000",
        "CALCulate:MARKer1:MAXimum",
    ]


def test_visa_analyzer_preconfigured_sweep_is_reused_for_marker_read(monkeypatch) -> None:
    monkeypatch.setattr(spectrum_analyzer.time, "sleep", lambda _: None)
    instrument = FakeVisaInstrument()
    analyzer = VisaSpectrumAnalyzer("SIM", sweep_span_ghz=1.0, frequency_divisor=10.0)
    analyzer._instrument = instrument

    analyzer.configure_sweep_for_frequency(215.0)
    analyzer.read_peak_power_dbm(make_context(215.0))

    assert instrument.writes == [
        "SENSe:FREQuency:CENTer 21500000000",
        "SENSe:FREQuency:SPAN 100000000",
        "CALCulate:MARKer1:MAXimum",
    ]


def test_visa_analyzer_connect_reports_available_resources(monkeypatch) -> None:
    resource_manager = FailingResourceManager()
    monkeypatch.setitem(sys.modules, "pyvisa", SimpleNamespace(ResourceManager=lambda: resource_manager))
    analyzer = VisaSpectrumAnalyzer("TCPIP::10.18.18.4::INSTR")

    with pytest.raises(RuntimeError) as exc_info:
        analyzer.connect()

    message = str(exc_info.value)
    assert "TCPIP::10.18.18.4::INSTR" in message
    assert "TCPIP0::10.18.18.4::inst0::INSTR" in message
    assert analyzer._rm is None
    assert resource_manager.closed


def test_visa_analyzer_connect_tries_standard_tcpip_inst0_fallback(monkeypatch) -> None:
    resource_manager = FallbackResourceManager()
    monkeypatch.setitem(sys.modules, "pyvisa", SimpleNamespace(ResourceManager=lambda: resource_manager))
    analyzer = VisaSpectrumAnalyzer("TCPIP::10.18.18.4::INSTR")

    analyzer.connect()

    assert resource_manager.opened == [
        "TCPIP::10.18.18.4::INSTR",
        "TCPIP0::10.18.18.4::inst0::INSTR",
    ]
    assert analyzer.address == "TCPIP0::10.18.18.4::inst0::INSTR"
    assert analyzer.is_connected()


def test_visa_analyzer_connect_tries_hislip_after_configured_inst0_fails(monkeypatch) -> None:
    resource_manager = ProtocolFallbackResourceManager("TCPIP0::10.18.18.4::hislip0::INSTR")
    monkeypatch.setitem(sys.modules, "pyvisa", SimpleNamespace(ResourceManager=lambda: resource_manager))
    analyzer = VisaSpectrumAnalyzer("TCPIP0::10.18.18.4::inst0::INSTR")

    analyzer.connect()

    assert resource_manager.opened == [
        "TCPIP0::10.18.18.4::inst0::INSTR",
        "TCPIP0::10.18.18.4::hislip0::INSTR",
    ]
    assert analyzer.address == "TCPIP0::10.18.18.4::hislip0::INSTR"
    assert analyzer.is_connected()


def test_visa_analyzer_connect_tries_socket_after_instrument_protocols_fail(monkeypatch) -> None:
    resource_manager = ProtocolFallbackResourceManager("TCPIP0::10.18.18.4::5025::SOCKET")
    monkeypatch.setitem(sys.modules, "pyvisa", SimpleNamespace(ResourceManager=lambda: resource_manager))
    analyzer = VisaSpectrumAnalyzer("TCPIP0::10.18.18.4::inst0::INSTR")

    analyzer.connect()

    assert resource_manager.opened == [
        "TCPIP0::10.18.18.4::inst0::INSTR",
        "TCPIP0::10.18.18.4::hislip0::INSTR",
        "TCPIP0::10.18.18.4::5025::SOCKET",
    ]
    assert analyzer.address == "TCPIP0::10.18.18.4::5025::SOCKET"
    assert resource_manager.instrument.write_termination == "\n"
    assert resource_manager.instrument.read_termination == "\n"
    assert analyzer.is_connected()


def test_xian_gpib_analyzer_sets_sweep_range_before_single_sweep() -> None:
    instrument = FakeVisaInstrument()
    analyzer = XianGpibSpectrumAnalyzer("SIM", sweep_span_ghz=1.5)
    analyzer._instrument = instrument
    analyzer._connected = True

    power_dbm = analyzer.read_peak_power_dbm(make_context(215.0))

    assert power_dbm == -12.5
    assert instrument.writes == [
        "INIT:CONT OFF",
        "SENSe:FREQuency:CENTer 215000000000",
        "SENSe:FREQuency:SPAN 1500000000",
        "INIT",
        "CALC:MARK:MAX",
    ]
    assert instrument.queries == ["*OPC?", "CALC:MARK:Y?"]
