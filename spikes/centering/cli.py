"""CLI for the centering spike: measure a card image, or a synthetic demo card.

    python cli.py path/to/card.png
    python cli.py --demo 60 40 55 45      # synthetic card at known L/R/T/B borders
"""

from __future__ import annotations

import argparse
import sys

from centering import CenteringError, load_grayscale, measure_centering
from synthetic import make_card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("image", nargs="?", help="path to a flat, deskewed card image")
    source.add_argument(
        "--demo",
        nargs=4,
        type=int,
        metavar=("LEFT", "RIGHT", "TOP", "BOTTOM"),
        help="generate a synthetic card with these border widths and measure it",
    )
    args = parser.parse_args(argv)

    if args.demo:
        card = make_card(borders=tuple(args.demo))
        field = card.image
        print(
            f"Synthetic card — ground-truth borders {tuple(args.demo)} "
            f"(L/R {card.expected_lr}, T/B {card.expected_tb})\n"
        )
    else:
        try:
            field = load_grayscale(args.image)
        except (OSError, ValueError) as exc:
            print(f"Could not read image: {exc}", file=sys.stderr)
            return 2

    try:
        result = measure_centering(field)
    except CenteringError as exc:
        print(f"Centering not measurable: {exc}", file=sys.stderr)
        return 3

    print(result.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
