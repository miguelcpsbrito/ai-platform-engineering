"""Figure 3.3's arithmetic, recomputed: the book's numbers must follow from its inputs."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "cost-model"))
from model_plane_tco import Inputs, compute, report  # noqa: E402


def test_figure_3_3_numbers():
    r = compute(Inputs())
    assert r["managed_usd_per_1m"] == pytest.approx(20, abs=0.1)
    assert r["self_hw_usd"] == pytest.approx(47_000, rel=0.02)
    assert r["capacity_b"] == pytest.approx(6.8, abs=0.05)
    assert r["self_total_usd"] == pytest.approx(75_000, rel=0.02)
    assert r["self_vs_managed"] == pytest.approx(1.8, abs=0.05)
    assert r["breakeven_util_with_fte"] == pytest.approx(0.55, abs=0.01)
    assert r["breakeven_util_without_fte"] == pytest.approx(0.35, abs=0.01)
    assert "Neither condition held at 31%" in report(Inputs())
