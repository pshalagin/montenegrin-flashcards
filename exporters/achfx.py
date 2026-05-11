#!/usr/bin/env python3
"""ACHFX SQLite exporter."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from flashcards import Card, Deck, OUT_DIR


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    lexorank    TEXT    NOT NULL DEFAULT '',
    preview     BLOB,
    queryImage1 BLOB,
    queryImage2 BLOB,
    queryText   varchar(150),
    querySound  BLOB,
    answerText  varchar(150),
    answerSound BLOB,
    tags        jsonb,
    settings    jsonb,
    draft       INTEGER NOT NULL DEFAULT 0
);
"""

INSERT_SQL = """
INSERT INTO cards
    (lexorank, preview, queryImage1, queryImage2,
     queryText, querySound, answerText, answerSound,
     tags, settings, draft)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def lexorank(n: int, total: int = 1000) -> str:
    """Generate a simple sortable rank string for card n (1-based)."""
    chars = "abcdefghijklmnopqrstuvwxyz"
    base = len(chars)
    value = int((n / (total + 1)) * (base**4))
    result = []

    for _ in range(4):
        result.append(chars[value % base])
        value //= base

    return "".join(reversed(result))


def truncate(text: str | None, limit: int = 9000) -> str | None:
    if text is None:
        return None
    return text[:limit]


class AchfxExporter:
    name = "achfx"
    default_output = OUT_DIR / "Montenegrin_1000.achfx"

    def export(self, deck: Deck, output_path: Path, options=None) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            output_path.unlink()

        conn = sqlite3.connect(output_path)
        conn.executescript(CREATE_SQL)

        try:
            with conn:
                for index, card in enumerate(deck.cards, start=1):
                    conn.execute(INSERT_SQL, self._row(card, index, len(deck.cards)))

                    if index % 100 == 0:
                        print(f"  Inserted {index}/{len(deck.cards)} ...")
        finally:
            conn.close()

        size_mb = output_path.stat().st_size / 1_048_576
        print(f"\n  Wrote {output_path} ({len(deck.cards)} cards, {size_mb:.1f} MB)")

    def _row(self, card: Card, index: int, total: int) -> tuple:
        if card.image_path is None or card.audio_path is None:
            raise ValueError(f"{card.source_path}: missing media path")

        return (
            lexorank(index, total),
            None,
            card.image_path.read_bytes(),
            None,
            truncate(card.front_text, 148),
            None,
            truncate(card.back_text, 9000),
            card.audio_path.read_bytes(),
            None,
            "null",
            0,
        )
