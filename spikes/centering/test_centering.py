"""Coverage for the centering measurement, asserted against synthetic ground truth.

Each test draws a card with *known* border widths and checks the recovered ratio, band,
and confidence. Synthetic cards give us exact labels, so we can pin the geometry to a
tight pixel tolerance rather than eyeballing real photos.
"""

from __future__ import annotations

import numpy as np
import pytest

from centering import (
    CenteringError,
    QualityBand,
    Ratio,
    _classify,
    _to_ratio,
    load_grayscale,
    measure_centering,
)
from synthetic import make_card

# The 1-D gradient locates each border to within ~1px; allow a small ratio slack so a
# single-pixel detection wobble near the edge guard doesn't flake the suite.
_RATIO_TOLERANCE = 2


def _close(measured: Ratio, expected: tuple[int, int]) -> bool:
    return abs(measured.high - expected[0]) <= _RATIO_TOLERANCE


def test_perfectly_centered_card_reads_50_50_pristine() -> None:
    card = make_card(borders=(40, 40, 40, 40))
    result = measure_centering(card.image)

    assert result.left_right == Ratio(50, 50)
    assert result.top_bottom == Ratio(50, 50)
    assert result.band is QualityBand.PRISTINE
    assert result.worst_offset == pytest.approx(0.0)
    assert result.confidence > 0.9


def test_horizontal_offset_recovers_known_ratio() -> None:
    # 48/32 px left-right == a 60/40 split: left border 1.5x the right.
    card = make_card(borders=(48, 32, 45, 45))
    result = measure_centering(card.image)

    assert card.expected_lr == (60, 40)
    assert _close(result.left_right, card.expected_lr)
    assert result.left_right.high > result.left_right.low
    assert result.top_bottom == Ratio(50, 50)
    assert result.band is QualityBand.EXCELLENT


def test_vertical_offset_recovers_known_ratio() -> None:
    card = make_card(borders=(45, 45, 70, 30))
    result = measure_centering(card.image)

    assert _close(result.top_bottom, card.expected_tb)
    assert result.left_right == Ratio(50, 50)


def test_worst_axis_drives_the_band() -> None:
    # L/R is fine (~52/48) but T/B is severe (~78/22): the band must follow the worse axis.
    card = make_card(borders=(42, 38, 90, 25))
    result = measure_centering(card.image)

    assert result.band is QualityBand.SEVERE
    assert result.top_bottom.high >= 75


@pytest.mark.parametrize(
    ("borders", "band"),
    [
        ((40, 40, 40, 40), QualityBand.PRISTINE),
        ((48, 32, 40, 40), QualityBand.EXCELLENT),  # 60/40
        ((52, 28, 40, 40), QualityBand.GOOD),  # ~65/35
        ((60, 20, 40, 40), QualityBand.OFF_CENTER),  # 75/25
        ((72, 12, 40, 40), QualityBand.SEVERE),  # ~86/14
    ],
)
def test_band_thresholds(borders: tuple[int, int, int, int], band: QualityBand) -> None:
    result = measure_centering(make_card(borders=borders).image)
    assert result.band is band


def test_measurement_survives_sensor_noise() -> None:
    card = make_card(borders=(60, 30, 45, 45), noise=6.0, seed=7)
    result = measure_centering(card.image)

    assert _close(result.left_right, card.expected_lr)
    assert result.confidence > 0.6  # noisier edges, but still a confident read


def test_off_center_card_is_high_confidence_not_low() -> None:
    # Confidence rates measurement quality, not centering quality: a cleanly-measured
    # badly-centred card must read as confident.
    result = measure_centering(make_card(borders=(60, 20, 45, 45)).image)  # 75/25
    assert result.band is QualityBand.OFF_CENTER
    assert result.confidence > 0.85


def test_full_bleed_card_has_no_separable_border() -> None:
    # A card on a contrasting background but with a uniform face (no printed border / art
    # panel) — a full-bleed design. There is no inner transition to lock onto.
    field = np.full((400, 300), 30.0)
    field[24:376, 24:276] = 200.0
    with pytest.raises(CenteringError):
        measure_centering(field)


def test_non_2d_input_is_rejected() -> None:
    with pytest.raises(CenteringError):
        measure_centering(np.zeros((100, 100, 3)))


def test_tiny_image_is_rejected() -> None:
    with pytest.raises(CenteringError):
        measure_centering(np.zeros((8, 8)))


def test_to_ratio_snaps_near_perfect_to_50_50() -> None:
    assert _to_ratio(100, 100) == Ratio(50, 50)
    assert _to_ratio(100, 101) == Ratio(50, 50)  # within tolerance
    assert _to_ratio(0, 0) == Ratio(50, 50)  # degenerate, no division by zero


def test_classify_uses_the_worse_axis() -> None:
    assert _classify(Ratio(52, 48), Ratio(70, 30)) is QualityBand.OFF_CENTER
    assert _classify(Ratio(55, 45), Ratio(55, 45)) is QualityBand.PRISTINE


def test_low_contrast_border_lowers_confidence_but_keeps_the_ratio() -> None:
    # A faint border↔art transition is still geometrically locatable, so the ratio holds,
    # but the read is reported as less certain.
    card = make_card(borders=(40, 40, 40, 40), card_value=140.0, art_value=120.0)
    result = measure_centering(card.image)

    assert result.left_right == Ratio(50, 50)
    assert result.confidence < 0.5


def test_recovers_borders_exactly_across_a_randomised_sweep() -> None:
    # The geometric core should be bias-free: over many random offsets and noise levels,
    # every border width is recovered to the pixel.
    rng = np.random.default_rng(0)
    for _ in range(400):
        borders = tuple(int(rng.integers(15, 80)) for _ in range(4))
        card = make_card(borders=borders, noise=float(rng.uniform(0, 6)), seed=int(rng.integers(1 << 20)))
        result = measure_centering(card.image)
        assert result.borders_px == borders


def test_measures_a_real_png_round_trip(tmp_path) -> None:
    # Exercise the file-decode path: render, save as PNG, reload via Pillow, measure.
    from PIL import Image

    card = make_card(borders=(48, 32, 45, 45))
    path = tmp_path / "card.png"
    Image.fromarray(card.image.astype(np.uint8), mode="L").save(path)

    result = measure_centering(load_grayscale(path))
    assert _close(result.left_right, (60, 40))
    assert result.band is QualityBand.EXCELLENT
