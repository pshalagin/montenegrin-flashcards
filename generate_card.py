#!/usr/bin/env python3
"""
generate_card.py
────────────────
Generates ONE flashcard: GPT-4o-mini answer text + DALL-E 3 image + TTS audio.
Writes media files under out/media/ and updates the card JSON in place.

Usage:
    # Generate card 0042
    python3 generate_card.py cards/0042_biti.json

    # Regenerate even if already done (--force)
    python3 generate_card.py cards/0042_biti.json --force

Environment:
    OPENAI_API_KEY   required
"""

import sys, os, json, base64, time, argparse
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    sys.exit("pip install openai")

API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: set OPENAI_API_KEY environment variable")

client = OpenAI(api_key=API_KEY)

# ── Models & settings ─────────────────────────────────────────────────────────
GPT_MODEL    = "gpt-4o-mini"
DALLE_MODEL  = "dall-e-3"
DALLE_SIZE   = "1024x1024"
DALLE_STYLE  = "vivid"
TTS_MODEL    = "tts-1"
TTS_VOICE    = "nova"          # nova = clear feminine, alloy = neutral
MAX_RETRIES  = 5
RETRY_DELAY  = 10
MEDIA_DIR    = Path("out") / "media"


# ── Prompt templates ──────────────────────────────────────────────────────────

ANSWER_SYSTEM = """\
You are a professional Montenegrin/Serbian language teacher creating flashcard backs for a \
Russian-speaking learner.

Write explanations in Russian. Use Montenegrin/Serbian for the target word, forms, examples, \
collocations, and short target-language phrases. Every Montenegrin/Serbian example sentence \
must have a Russian translation.

Output Markdown only:
- use Markdown headings, short paragraphs, and bullet or numbered lists;
- do NOT use tables of any kind;
- do NOT use HTML, code fences, or box-drawing characters.

Keep it dense but clear.
"""

ANSWER_PROMPT_TEMPLATE = """\
Create the ANSWER side of a Montenegrin/Serbian vocabulary flashcard.

Word: {montenegrin}
Russian translation: {russian}
Part of speech: {pos}
Disambiguation: {context_ru}

Produce the following sections in this exact order, separated by blank lines:

## {montenegrin} — {russian}
- Part of speech: {pos}
- Short Russian explanation of meaning and usage.

## Грамматика и формы
- For NOUNS: give gender and the key singular/plural case forms as bullet lists, not a table.
- For VERBS: give aspect, infinitive, present forms for all persons, past forms, imperative, \
and verbal noun if common, as nested bullet lists, not a table.
- For ADJECTIVES: give masculine/feminine/neuter forms, common case forms, comparative, \
and superlative as bullet lists, not a table.
- For ADVERBS / PREPOSITIONS / CONJUNCTIONS: list the main constructions and usage notes.
- For PRONOUNS & NUMERALS: list the important declined forms as bullets, not a table.
- Explain grammar notes in Russian.

## Примеры
Write exactly 3 numbered examples:
1. Simple everyday Montenegrin sentence — Russian translation.
2. Slightly more complex sentence showing another form or meaning — Russian translation.
3. Idiomatic or collocational use if applicable — Russian translation.

## Сочетания, синонимы и антонимы
- Give 2–4 useful items.
- Format each item as: Montenegrin item — Russian explanation.

Keep total length under 600 words. Use clear, accurate Montenegrin and natural Russian.
"""

IMAGE_PROMPT_TEMPLATE = """\
Create one clear educational flashcard illustration for this vocabulary concept.

Target word: {montenegrin}
Russian meaning: {russian}
Part of speech: {pos}
Meaning/context in Russian: {context_ru}

Illustration rules:
- Illustrate the core concept directly, not a full narrative scene.
- Prefer one central, recognizable subject or action.
- Keep the composition simple enough to understand at thumbnail size.
- Use a flat vector style, clean minimal design, white background, friendly educational look.
- Use vibrant but not garish colors.
- Do not include text, letters, numbers, labels, speech bubbles, captions, flags, or UI.
- Avoid visual clutter, surreal combinations, and unnecessary background details.
- If the concept is abstract, use a simple universal visual metaphor.

Optional semantic hint from the card data:
{dalle_prompt}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def retry(fn, *args, **kwargs):
    """Call fn with retries on rate-limit / server errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if attempt == MAX_RETRIES:
                raise
            if "rate_limit" in msg.lower() or "529" in msg or "500" in msg:
                wait = RETRY_DELAY * attempt
                print(f"    ⚠  Retry {attempt}/{MAX_RETRIES} after {wait}s: {msg[:80]}")
                time.sleep(wait)
            else:
                raise


def generate_answer_text(card: dict) -> str:
    prompt = ANSWER_PROMPT_TEMPLATE.format(
        montenegrin=card["montenegrin"],
        russian=card["russian"],
        pos=card["pos"],
        context_ru=card["context_ru"],
    )
    response = retry(
        client.chat.completions.create,
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=900,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def detect_image_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return ".img"


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def write_media_file(card_path: Path, suffix: str, data: bytes) -> str:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    media_path = MEDIA_DIR / f"{card_path.stem}{suffix}"
    media_path.write_bytes(data)
    if media_path.read_bytes() != data:
        raise OSError(f"Verification failed after writing {media_path}")
    return relative_path(media_path)


def generate_image_bytes(card: dict) -> bytes:
    """Returns generated image bytes."""
    full_prompt = IMAGE_PROMPT_TEMPLATE.format(
        montenegrin=card["montenegrin"],
        russian=card["russian"],
        pos=card["pos"],
        context_ru=card["context_ru"],
        dalle_prompt=card["dalle_prompt"],
    )
    response = retry(
        client.images.generate,
        model=DALLE_MODEL,
        prompt=full_prompt,
        n=1,
        size=DALLE_SIZE,
        style=DALLE_STYLE,
        response_format="b64_json",
    )
    return base64.b64decode(response.data[0].b64_json)


def generate_audio_bytes(word: str) -> bytes:
    """Returns AAC audio bytes."""
    response = retry(
        client.audio.speech.create,
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=word,
        response_format="aac",
    )
    return response.read()


# ── Main ──────────────────────────────────────────────────────────────────────

def process_card(path: Path, force: bool = False):
    card = json.loads(path.read_text("utf-8"))

    if card.get("status") == "done" and not force:
        print(f"  ✓ Already done: {path.name}")
        return

    word = card["montenegrin"]
    print(f"  ▶ {path.name}  [{word}  →  {card['russian']}]")

    card["status"] = "generating"
    path.write_text(json.dumps(card, ensure_ascii=False, indent=2), "utf-8")

    try:
        # 1. GPT answer text
        print(f"    · GPT answer text …", end=" ", flush=True)
        card["answer_text"] = generate_answer_text(card)
        print("✓")

        # 2. DALL-E image
        print(f"    · DALL-E image …", end=" ", flush=True)
        image_bytes = generate_image_bytes(card)
        card["image_file"] = write_media_file(
            path,
            detect_image_extension(image_bytes),
            image_bytes,
        )
        print("✓")

        # 3. TTS audio
        print(f"    · TTS audio …", end=" ", flush=True)
        audio_bytes = generate_audio_bytes(word)
        card["audio_file"] = write_media_file(path, ".aac", audio_bytes)
        print("✓")

        card["status"] = "done"
        card["error"]  = None

    except Exception as e:
        card["status"] = "error"
        card["error"]  = str(e)
        print(f"\n    ✗ ERROR: {e}")

    path.write_text(json.dumps(card, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate one flashcard")
    parser.add_argument("card", help="Path to a card JSON file, e.g. cards/0001_biti.json")
    parser.add_argument("--force", action="store_true", help="Regenerate even if already done")
    args = parser.parse_args()

    process_card(Path(args.card), force=args.force)
