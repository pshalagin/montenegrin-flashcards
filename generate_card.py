#!/usr/bin/env python3
"""
generate_card.py
────────────────
Generates ONE flashcard: GPT-4o-mini answer text + DALL-E 3 image + TTS audio.
Updates the card's JSON stub in place.

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


# ── Prompt templates ──────────────────────────────────────────────────────────

ANSWER_SYSTEM = """\
You are a professional Montenegrin/Serbian language teacher creating flashcard backs for a \
Russian-speaking learner. Your output will be stored as plain UTF-8 text in a mobile app. \
Do NOT use Markdown headers (###), do NOT use HTML. Use plain text with Unicode box-drawing \
characters for tables if helpful. Keep it dense but clear.
"""

ANSWER_PROMPT_TEMPLATE = """\
Create the ANSWER side of a Montenegrin/Serbian vocabulary flashcard.

Word: {montenegrin}
Russian translation: {russian}
Part of speech: {pos}
Disambiguation: {context_ru}

Produce the following sections in this exact order, separated by blank lines:

1. TRANSLATION LINE
   Format:  {montenegrin} — {russian}  [{pos}]

2. GRAMMAR & FORMS
   For NOUNS: gender, declension table (sing + plur, all 7 cases: Nom Gen Dat Acc Voc Ins Lok)
   For VERBS: aspect (sov/nesov), infinitive, present tense all 6 persons (ja/ti/on/mi/vi/oni), \
past tense (m/f/n sing + plur), imperative (sing + plur), verbal noun if common
   For ADJECTIVES: declension (m/f/n sing nom, gen, dat; plur nom), comparative & superlative
   For ADVERBS / PREPOSITIONS / CONJUNCTIONS: list the main constructions/uses with short notes
   For PRONOUNS & NUMERALS: full declension table

3. EXAMPLE SENTENCES  (exactly 3)
   Each: Montenegrin sentence → Russian translation
   – Sentence 1: simple, everyday use
   – Sentence 2: slightly more complex, shows a different word form or meaning
   – Sentence 3: idiomatic or collocational use if applicable

4. COLLOCATIONS / SYNONYMS / ANTONYMS  (2–4 items, whichever is relevant)
   Format:  • item — explanation in Russian

Keep total length under 600 words. Write in clear, accurate Montenegrin.
"""

DALLE_SYSTEM_PREFIX = (
    "Flat vector illustration, clean minimal design, white background, "
    "no text, no letters, no numbers, friendly and educational style, "
    "vibrant but not garish colors. Scene: "
)


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


def generate_image_b64(card: dict) -> str:
    """Returns base64-encoded JPEG bytes."""
    full_prompt = DALLE_SYSTEM_PREFIX + card["dalle_prompt"]
    response = retry(
        client.images.generate,
        model=DALLE_MODEL,
        prompt=full_prompt,
        n=1,
        size=DALLE_SIZE,
        style=DALLE_STYLE,
        response_format="b64_json",
    )
    return response.data[0].b64_json          # already base64 string


def generate_audio_b64(word: str) -> str:
    """Returns base64-encoded AAC/MP4 audio bytes."""
    response = retry(
        client.audio.speech.create,
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=word,
        response_format="aac",
    )
    raw_bytes = response.read()
    return base64.b64encode(raw_bytes).decode("ascii")


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
        card["image_b64"] = generate_image_b64(card)
        print("✓")

        # 3. TTS audio
        print(f"    · TTS audio …", end=" ", flush=True)
        card["audio_b64"] = generate_audio_b64(word)
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
    parser.add_argument("card", help="Path to a card JSON stub, e.g. cards/0001_biti.json")
    parser.add_argument("--force", action="store_true", help="Regenerate even if already done")
    args = parser.parse_args()

    process_card(Path(args.card), force=args.force)
