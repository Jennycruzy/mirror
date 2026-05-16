import pytest

from mirror.calibration.brier import brier_score, calibration_buckets, direction_to_probability_up


def test_direction_to_probability_up():
    assert direction_to_probability_up("long", 0.7) == 0.7
    assert direction_to_probability_up("short", 0.7) == pytest.approx(0.3)
    assert direction_to_probability_up("flat", 0.9) == 0.5


def test_brier_score():
    assert brier_score(0.7, "up") == (0.7 - 1) ** 2
    assert brier_score(0.7, "down") == 0.7**2


def test_calibration_buckets():
    buckets = calibration_buckets([(0.05, 0), (0.95, 1)])
    assert buckets[0].count == 1
    assert buckets[-1].count == 1
