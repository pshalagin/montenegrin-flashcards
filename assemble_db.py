#!/usr/bin/env python3
"""
assemble_db.py
──────────────
Reads all  cards/*.json  files with status="done"  and assembles them
into  Montenegrin_1000.achfx  — a SQLite database in the exact same
schema as the sample Montenegrin_2026-05-05.achfx file.

Schema (from reverse-engineering the sample):

    CREATE TABLE cards (
        id          INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        lexorank    TEXT    NOT NULL DEFAULT '',
        preview     BLOB,           -- small thumbnail JPEG (optional)
        queryImage1 BLOB,           -- JPEG bytes shown on front
        queryImage2 BLOB,           -- unused
        queryText   varchar(150),   -- Russian word + hint (front text)
        querySound  BLOB,           -- unused
        answerText  varchar(150),   -- Montenegrin + full grammar (back text)
        answerSound BLOB,           -- AAC/MP4 audio bytes
        tags        jsonb,
        settings    jsonb,
        draft       INTEGER NOT NULL DEFAULT 0
    )

Usage:
    python3 assemble_db.py                        # produces Montenegrin_1000.achfx
    python3 assemble_db.py --output my_deck.achfx # custom filename
    python3 assemble_db.py --include-errors       # also add error cards as drafts
    python3 assemble_db.py --status               # just show counts, don't build

Notes:
  - Cards are inserted in the order of their numeric ID (0001 … 1000).
  - lexorank is auto-generated as a simple sortable string.
  - Partial assemblies are safe — re-running overwrites the output file.
"""

import argparse, base64, json, sqlite3
from pathlib import Path

CARDS_DIR   = Path("cards")
OUTPUT_FILE = "Montenegrin_1000.achfx"

# ── LexoRank helper ───────────────────────────────────────────────────────────
# LexoRank encodes a sort position as a base-36 string.
# The sample card uses "mzz" — we'll use a simple incrementing scheme
# that gives room for manual reordering later.

def lexorank(n: int, total: int = 1000) -> str:
    """Generate a simple sortable rank string for card n (1-based)."""
    # Map 1..total → lowercase letters 'a'..'z', repeating for longer keys
    # We use 4-char base-26 strings: 'aaaa' … 'zzzz'
    chars = "abcdefghijklmnopqrstuvwxyz"
    base = len(chars)

    # Scale n to fit within base^4 space with padding
    value = int((n / (total + 1)) * (base ** 4))
    result = []
    for _ in range(4):
        result.append(chars[value % base])
        value //= base
    return "".join(reversed(result))


# ── DB helpers ────────────────────────────────────────────────────────────────

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
CREATE TABLE IF NOT EXISTS sqlite_sequence (name, seq);
"""

INSERT_SQL = """
INSERT INTO cards
    (lexorank, preview, queryImage1, queryImage2,
     queryText, querySound, answerText, answerSound,
     tags, settings, draft)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def decode_b64_or_none(s) -> bytes | None:
    if not s:
        return None
    try:
        return base64.b64decode(s)
    except Exception:
        return None


def truncate(text: str | None, limit: int = 9000) -> str | None:
    """SQLite varchar(150) is advisory, but keep answer text reasonable."""
    if text is None:
        return None
    return text[:limit]


# ── Main ──────────────────────────────────────────────────────────────────────

def load_cards(include_errors: bool) -> list[dict]:
    paths = sorted(CARDS_DIR.glob("*.json"))
    cards = []
    for p in paths:
        try:
            data = json.loads(p.read_text("utf-8"))
        except Exception as e:
            print(f"  ⚠ Could not read {p.name}: {e}")
            continue

        status = data.get("status", "")
        if status == "done":
            data["_draft"] = 0
            cards.append(data)
        elif status == "error" and include_errors:
            data["_draft"] = 1   # show as draft in app
            cards.append(data)

    return cards


def build_db(output_path: Path, cards: list[dict]):
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(output_path)
    conn.executescript(CREATE_SQL)

    total = len(cards)
    inserted = 0

    with conn:
        for i, card in enumerate(cards, start=1):
            rank        = lexorank(i, total)
            image_bytes = decode_b64_or_none(card.get("image_b64"))
            audio_bytes = decode_b64_or_none(card.get("audio_b64"))
            query_text  = truncate(card.get("query_text"), 148)
            answer_text = truncate(card.get("answer_text"), 9000)

            conn.execute(INSERT_SQL, (
                rank,
                None,           # preview — we don't generate thumbnails
                image_bytes,    # queryImage1  ← DALL-E JPEG
                None,           # queryImage2
                query_text,     # queryText    ← Russian + hint
                None,           # querySound
                answer_text,    # answerText   ← grammar + sentences
                audio_bytes,    # answerSound  ← TTS
                None,           # tags
                "null",         # settings
                card.get("_draft", 0),
            ))
            inserted += 1

            if inserted % 100 == 0:
                print(f"  Inserted {inserted}/{total} …")

    conn.close()
    size_mb = output_path.stat().st_size / 1_048_576
    print(f"\n  ✓ {output_path}  ({inserted} cards, {size_mb:.1f} MB)")


def show_status():
    paths = sorted(CARDS_DIR.glob("*.json"))
    counts = {"pending": 0, "generating": 0, "done": 0, "error": 0, "other": 0}
    for p in paths:
        try:
            s = json.loads(p.read_text()).get("status", "other")
            counts[s if s in counts else "other"] += 1
        except Exception:
            counts["other"] += 1
    total = sum(counts.values())
    pct = counts["done"] / total * 100 if total else 0
    print(f"\n  Card status ({total} total):")
    for k, v in counts.items():
        bar = "█" * int(v / max(total, 1) * 30)
        print(f"    {k:12s}  {v:5d}  {bar}")
    print(f"\n  Completion: {pct:.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble flashcard SQLite database")
    parser.add_argument("--output",         default=OUTPUT_FILE,
                        help=f"Output .achfx filename (default: {OUTPUT_FILE})")
    parser.add_argument("--include-errors", action="store_true",
                        help="Include errored cards as draft entries")
    parser.add_argument("--status",         action="store_true",
                        help="Show card status counts and exit")
    args = parser.parse_args()

    if args.status:
        show_status()
        raise SystemExit(0)

    show_status()

    cards = load_cards(include_errors=args.include_errors)
    if not cards:
        print("\n  No done cards found. Run generate_all.py first.")
        raise SystemExit(1)

    output_path = Path(args.output)
    print(f"\n  Building {output_path} from {len(cards)} cards …\n")
    build_db(output_path, cards)
    print(f"\n  Done! Import {output_path} into your flashcard app.")
