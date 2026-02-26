import pytest

from openatoms.units import Quantity, as_temp_c, as_time_s, as_volume_ml


def test_volume_unit_conversions():
    assert Quantity(1, "l", "volume").to("ml").value == pytest.approx(1000.0)
    assert Quantity(250, "ml", "volume").to("l").value == pytest.approx(0.25)
    assert as_volume_ml(Quantity(0.5, "l", "volume")) == pytest.approx(500.0)


def test_temperature_unit_conversions():
    assert Quantity(300.0, "k", "temperature").to("c").value == pytest.approx(26.85)
    assert as_temp_c(Quantity(273.15, "k", "temperature")) == pytest.approx(0.0)


def test_time_unit_conversions():
    assert Quantity(2, "min", "time").to("s").value == pytest.approx(120.0)
    assert as_time_s(Quantity(1, "h", "time")) == pytest.approx(3600.0)


def test_dimensional_mismatch_rejected():
    with pytest.raises(ValueError):
        as_volume_ml(Quantity(50, "c", "temperature"))
