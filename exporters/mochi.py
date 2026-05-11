#!/usr/bin/env python3
"""Native .mochi ZIP exporter."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from flashcards import Card, Deck, OUT_DIR


DECK_ID = ":mfcdeck01"


def edn_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def card_keyword(card: Card) -> str:
    return f":mfccard{card.id:04d}"


def markdown_content(card: Card, media_names: tuple[str, str]) -> str:
    image_name, audio_name = media_names
    front = "\n\n".join(
        part
        for part in (
            f"![Illustration](media/{image_name})",
            (card.front_text or "").strip(),
        )
        if part
    )
    back = "\n\n".join(
        part
        for part in (
            (card.back_text or "").strip(),
            f"![Audio](media/{audio_name})",
        )
        if part
    )
    return f"{front}\n\n---\n\n{back}"


class MochiExporter:
    name = "mochi"
    default_output = OUT_DIR / "Montenegrin_1000.mochi"

    def export(self, deck: Deck, output_path: Path, options=None) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        media_entries = self._media_entries(deck.cards)
        data_edn = self._data_edn(deck, media_entries)

        with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("data.edn", data_edn)

            for card in deck.cards:
                image_name, audio_name = media_entries[card.id]
                if card.image_path is None or card.audio_path is None:
                    raise ValueError(f"{card.source_path}: missing media path")
                archive.write(card.image_path, f"media/{image_name}")
                archive.write(card.audio_path, f"media/{audio_name}")

        size_mb = output_path.stat().st_size / 1_048_576
        print(
            f"\n  Wrote {output_path} "
            f"({len(deck.cards)} cards, {len(deck.cards) * 2} media files, {size_mb:.1f} MB)"
        )

    def _media_entries(self, cards: list[Card]) -> dict[int, tuple[str, str]]:
        entries = {}
        seen = set()

        for card in cards:
            if card.image_path is None or card.audio_path is None:
                raise ValueError(f"{card.source_path}: missing media path")

            image_name = f"{card.stem}{card.image_path.suffix.lower()}"
            audio_name = f"{card.stem}{card.audio_path.suffix.lower()}"

            for name in (image_name, audio_name):
                if name in seen:
                    raise ValueError(f"{card.source_path}: duplicate Mochi media name {name}")
                seen.add(name)

            entries[card.id] = (image_name, audio_name)

        return entries

    def _data_edn(self, deck: Deck, media_entries: dict[int, tuple[str, str]]) -> str:
        cards_edn = [self._card_edn(card, media_entries[card.id]) for card in deck.cards]
        cards_block = "\n      ".join(cards_edn)

        return (
            "{:version 2\n"
            " :decks [{:id " + DECK_ID + "\n"
            "          :name " + edn_string(deck.name) + "\n"
            "          :cards ["
            + cards_block
            + "]}]}\n"
        )

    def _card_edn(self, card: Card, media_names: tuple[str, str]) -> str:
        return (
            "{:id "
            + card_keyword(card)
            + "\n       :name "
            + edn_string(card.name)
            + "\n       :pos "
            + edn_string(card.sort_order)
            + "\n       :content "
            + edn_string(markdown_content(card, media_names))
            + "}"
        )
