"""Coverage for the promoted in-house centering measurement, against synthetic ground truth.

Ported from Spike D: each test draws a card with *known* border widths and checks the
recovered ratio, band, and confidence. Synthetic cards give exact labels, so the geometry
is pinned to a tight pixel tolerance rather than eyeballed. Also covers the production entry
point: ``measure_centering`` decoding the raw PNG bytes the API receives.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest

from app.grading.centering import (
    CenteringError,
    QualityBand,
    Ratio,
    measure_centering,
)
from tests.grading_synthetic import make_card

# The 1-D gradient locates each border to within ~1px; allow a small ratio slack so a
# single-pixel detection wobble near the edge guard doesn't flake the suite.
_RATIO_TOLERANCE = 2


def _close(measured: Ratio, expected: tuple[int, int]) -> bool:
    return abs(measured.high - expected[0]) <= _RATIO_TOLERANCE


def test_perfectly_centered_card_reads_50_50_pristine() -> None:
    result = measure_centering(make_card(borders=(40, 40, 40, 40)).image)

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


def test_worst_axis_drives_the_band() -> None:
    # L/R is fine (~52/48) but T/B is severe (~78/22): the band must follow the worse axis.
    result = measure_centering(make_card(borders=(42, 38, 90, 25)).image)

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
    assert measure_centering(make_card(borders=borders).image).band is band


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


def test_low_contrast_border_lowers_confidence_but_keeps_the_ratio() -> None:
    # A faint border↔art transition is still geometrically locatable, so the ratio holds,
    # but the read is reported as less certain.
    card = make_card(borders=(40, 40, 40, 40), card_value=140.0, art_value=120.0)
    result = measure_centering(card.image)

    assert result.left_right == Ratio(50, 50)
    assert result.confidence < 0.5


def test_full_bleed_card_has_no_separable_border() -> None:
    # A card on a contrasting background but with a uniform face — a full-bleed design. There
    # is no inner transition to lock onto, so the measurement refuses rather than inventing.
    field = np.full((400, 300), 30.0)
    field[24:376, 24:276] = 200.0
    with pytest.raises(CenteringError):
        measure_centering(field)


def test_non_2d_array_is_rejected() -> None:
    with pytest.raises(CenteringError):
        measure_centering(np.zeros((100, 100, 3)))


def test_tiny_image_is_rejected() -> None:
    with pytest.raises(CenteringError):
        measure_centering(np.zeros((8, 8)))


def test_recovers_borders_exactly_across_a_randomised_sweep() -> None:
    # The geometric core should be bias-free: over many random offsets and noise levels,
    # every border width is recovered to the pixel.
    rng = np.random.default_rng(0)
    for _ in range(200):
        borders = tuple(int(rng.integers(15, 80)) for _ in range(4))
        card = make_card(borders=borders, noise=float(rng.uniform(0, 6)), seed=int(rng.integers(1 << 20)))
        assert measure_centering(card.image).borders_px == borders


def test_decodes_raw_png_bytes_the_api_receives() -> None:
    # The production entry point: the API hands over encoded capture bytes, not an array.
    from PIL import Image

    card = make_card(borders=(48, 32, 45, 45))
    buffer = BytesIO()
    Image.fromarray(card.image.astype(np.uint8), mode="L").save(buffer, format="PNG")

    result = measure_centering(buffer.getvalue())
    assert _close(result.left_right, (60, 40))
    assert result.band is QualityBand.EXCELLENT


def test_undecodable_bytes_raise_centering_error() -> None:
    with pytest.raises(CenteringError):
        measure_centering(b"not an image")
