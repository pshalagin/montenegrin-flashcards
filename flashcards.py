#!/usr/bin/env python3
"""Shared card loading and normalized deck model."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable


CARDS_DIR = Path("cards")
OUT_DIR = Path("out")
DECK_NAME = "Montenegrin 1000"
DONE_STATUS = "done"
STATUS_KEYS = ("pending", "generating", "done", "error", "other")


@dataclass(frozen=True)
class Card:
    id: int
    name: str
    sort_order: str
    front_text: str | None
    back_text: str | None
    image_path: Path | None
    audio_path: Path | None
    status: str
    source_path: Path
    raw: dict

    @property
    def stem(self) -> str:
        return self.source_path.stem


@dataclass(frozen=True)
class Deck:
    name: str
    cards: list[Card]


def parse_card_id(path: Path, data: dict) -> int:
    value = data.get("id")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)

    stem_prefix = path.stem.split("_", 1)[0]
    if stem_prefix.isdigit():
        return int(stem_prefix)

    raise ValueError(f"{path}: missing numeric card id")


def resolve_media_path(card_path: Path, value: str | None) -> Path | None:
    if not value:
        return None

    media_path = Path(value)
    if media_path.is_absolute():
        return media_path

    if media_path.exists():
        return media_path

    return card_path.parent / media_path


def load_card(path: Path) -> Card:
    try:
        data = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        raise ValueError(f"{path}: could not read JSON: {exc}") from exc

    card_id = parse_card_id(path, data)
    name = str(data.get("montenegrin") or path.stem)
    status = str(data.get("status") or "other")

    return Card(
        id=card_id,
        name=name,
        sort_order=f"{card_id:04d}",
        front_text=data.get("query_text"),
        back_text=data.get("answer_text"),
        image_path=resolve_media_path(path, data.get("image_file")),
        audio_path=resolve_media_path(path, data.get("audio_file")),
        status=status,
        source_path=path,
        raw=data,
    )


def validate_generated_card(card: Card) -> None:
    missing = []

    if not card.front_text:
        missing.append("query_text")
    if not card.back_text:
        missing.append("answer_text")
    if card.image_path is None:
        missing.append("image_file")
    elif not card.image_path.exists():
        missing.append(f"image_file not found: {card.raw.get('image_file')}")
    if card.audio_path is None:
        missing.append("audio_file")
    elif not card.audio_path.exists():
        missing.append(f"audio_file not found: {card.raw.get('audio_file')}")

    if missing:
        detail = ", ".join(missing)
        raise ValueError(f"{card.source_path}: done card is not exportable ({detail})")


def load_cards(cards_dir: Path = CARDS_DIR, validate_done: bool = False) -> list[Card]:
    cards = []
    errors = []

    for path in sorted(cards_dir.glob("*.json")):
        try:
            card = load_card(path)
            if validate_done and card.status == DONE_STATUS:
                validate_generated_card(card)
            cards.append(card)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError("\n".join(errors))

    return sorted(cards, key=lambda card: (card.id, card.source_path.name))


def load_deck(
    cards_dir: Path = CARDS_DIR,
    statuses: Iterable[str] = (DONE_STATUS,),
    validate: bool = True,
    name: str = DECK_NAME,
) -> Deck:
    status_set = set(statuses)
    cards = [
        card
        for card in load_cards(cards_dir, validate_done=validate)
        if card.status in status_set
    ]
    return Deck(name=name, cards=cards)


def status_counts(cards_dir: Path = CARDS_DIR) -> dict[str, int]:
    counts = {key: 0 for key in STATUS_KEYS}

    for path in sorted(cards_dir.glob("*.json")):
        try:
            status = json.loads(path.read_text("utf-8")).get("status", "other")
            counts[status if status in counts else "other"] += 1
        except Exception:
            counts["other"] += 1

    return counts


def print_status(counts: dict[str, int]) -> None:
    total = sum(counts.values())
    done = counts.get("done", 0)
    pct = done / total * 100 if total else 0

    print(f"\n  Card status ({total} total):")
    for key in STATUS_KEYS:
        value = counts.get(key, 0)
        bar = "#" * int(value / max(total, 1) * 30)
        print(f"    {key:12s}  {value:5d}  {bar}")

    print(f"\n  Completion: {pct:.1f}%")
    print(
        f"  done={done}  pending={counts.get('pending', 0)}  "
        f"error={counts.get('error', 0)}  total={total}"
    )
