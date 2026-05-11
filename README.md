# Montenegrin / Serbian Flashcard Generator — 1000 cards

Generates flashcard decks for learning Montenegrin/Serbian from Russian.
The canonical storage format is `cards/*.json` plus media files under
`out/media/`; exporters can build app-specific deck files from the same
generated cards.

## Card format

**Front (query)**
- Russian word + part of speech + disambiguation hint
- DALL-E 3 illustration (1024 × 1024 flat-vector style)

**Back (answer)**
- Full grammar: declension / conjugation table for all forms
- 3 example sentences (Montenegrin → Russian)
- Collocations / synonyms / antonyms

**Audio** — TTS pronunciation of the Montenegrin word (nova voice)

Generated card JSON stores text plus reviewable media paths:
- `image_file`: generated illustration under `out/media/`, usually `.png`
- `audio_file`: generated pronunciation under `out/media/`, `.aac`

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your OpenAI API key
export OPENAI_API_KEY="sk-proj-..."
```

---

## Workflow

### Step 1 — Edit card content
Card JSON files under `cards/` are the source of truth. To add or change
vocabulary, edit those files directly.

Pending cards should include the generation inputs:
- `id`
- `montenegrin`
- `russian`
- `pos`
- `context_ru`
- `dalle_prompt`
- `status: "pending"`
- `query_text`
- `answer_text: null`
- `image_file: null`
- `audio_file: null`
- `error: null`

### Step 2 — Generate cards
```bash
# Generate everything (default 3 concurrent workers)
python3 generate_all.py

# Faster, higher rate-limit risk
python3 generate_all.py --workers 5

# Only a slice (useful for testing)
python3 generate_all.py --range 1 10

# Retry any that failed
python3 generate_all.py --retry-errors

# Check progress without running
python3 generate_all.py --dry-run
```

Each card calls three OpenAI APIs:
1. **GPT-4o-mini** → grammar table + 3 example sentences
2. **DALL-E 3** → 1024×1024 illustration file
3. **TTS-1** → AAC audio of the word

Results are saved immediately into the card JSON and `out/media/`,
so you can interrupt and resume at any time.

### Step 3 — Inspect individual cards
You can open any `cards/XXXX_word.json` and edit `answer_text` by hand,
or review the generated image/audio files under `out/media/`. You can also regenerate it:
```bash
python3 generate_card.py cards/0042_biti.json --force
```

### Step 4 — Export decks
```bash
python3 export.py status
python3 export.py achfx
python3 export.py mochi
```

Default outputs:
- `out/Montenegrin_1000.achfx` — SQLite ACHFX deck
- `out/Montenegrin_1000.mochi` — native Mochi ZIP import

```bash
# Custom output paths
python3 export.py achfx --output out/custom.achfx
python3 export.py mochi --output out/custom.mochi
```

`export.py` reads only generated cards with `status: done`. Done cards must have
`query_text`, `answer_text`, `image_file`, and `audio_file`; missing media fails
clearly.

## Exporters

Built-in exporters:
- `achfx` — writes the SQLite schema used by the current flashcard app.
- `mochi` — writes a native `.mochi` ZIP with `data.edn` and `media/` files.

Mochi cards are simple Markdown cards. The front side contains the illustration
and `query_text`; the back side contains `answer_text` and the audio reference,
with `---` separating the sides.

---

## Cost estimate

| API          | Per card | × 1000 |
|--------------|----------|--------|
| DALL-E 3     | $0.040   | $40.00 |
| GPT-4o-mini  | ~$0.0005 | $0.50  |
| TTS-1        | ~$0.003  | $3.00  |
| **Total**    |          | **≈ $43.50** |
