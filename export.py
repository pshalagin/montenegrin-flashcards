#!/usr/bin/env python3
"""Unified flashcard export CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from exporters import EXPORTERS, get_exporter
from flashcards import CARDS_DIR, DECK_NAME, load_deck, print_status, status_counts


def add_exporter_parser(subparsers, name: str, default_output: Path) -> None:
    parser = subparsers.add_parser(name, help=f"Export {name.upper()} deck")
    parser.add_argument(
        "--cards-dir",
        default=CARDS_DIR,
        type=Path,
        help=f"Card JSON directory (default: {CARDS_DIR})",
    )
    parser.add_argument(
        "--output",
        default=default_output,
        type=Path,
        help=f"Output file (default: {default_output})",
    )
    parser.add_argument(
        "--deck-name",
        default=DECK_NAME,
        help=f"Deck name (default: {DECK_NAME!r})",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Export generated flashcards")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show card generation status")
    status_parser.add_argument(
        "--cards-dir",
        default=CARDS_DIR,
        type=Path,
        help=f"Card JSON directory (default: {CARDS_DIR})",
    )

    for name, exporter in sorted(EXPORTERS.items()):
        add_exporter_parser(subparsers, name, exporter.default_output)

    args = parser.parse_args()

    if args.command == "status":
        print_status(status_counts(args.cards_dir))
        return 0

    exporter = get_exporter(args.command)
    deck = load_deck(cards_dir=args.cards_dir, validate=True, name=args.deck_name)

    if not deck.cards:
        print("\n  No done cards found. Run generate_all.py first.")
        return 1

    print(f"\n  Exporting {len(deck.cards)} done cards to {args.output} ...")
    exporter.export(deck, args.output, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
