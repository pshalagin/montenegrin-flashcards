# Montenegrin / Serbian Flashcard Generator — 1000 cards

Generates a complete `.achfx` flashcard deck (1000 cards) for learning
Montenegrin/Serbian from Russian.

## Card format

**Front (query)**
- Russian word + part of speech + disambiguation hint
- DALL-E 3 illustration (1024 × 1024 flat-vector style)

**Back (answer)**
- Full grammar: declension / conjugation table for all forms
- 3 example sentences (Montenegrin → Russian)
- Collocations / synonyms / antonyms

**Audio** — TTS pronunciation of the Montenegrin word (nova voice)

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

### Step 1 — Create stubs
```bash
python3 init_stubs.py
```
Creates `cards/0001_ja.json` … `cards/1000_….json` — one stub per word,
all with `status: pending`. Safe to re-run.

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
2. **DALL-E 3** → 1024×1024 JPEG illustration
3. **TTS-1** → AAC audio of the word

Results are saved immediately into the JSON stub, so you can interrupt
and resume at any time.

### Step 3 — Inspect individual cards
You can open any `cards/XXXX_word.json` and edit `answer_text` by hand,
or regenerate it:
```bash
python3 generate_card.py cards/0042_biti.json --force
```

### Step 4 — Assemble the database
```bash
python3 assemble_db.py
```
Produces `Montenegrin_1000.achfx` — a SQLite file ready to import.

```bash
# Check how many cards are done before assembling
python3 assemble_db.py --status
```

---

## Cost estimate

| API          | Per card | × 1000 |
|--------------|----------|--------|
| DALL-E 3     | $0.040   | $40.00 |
| GPT-4o-mini  | ~$0.0005 | $0.50  |
| TTS-1        | ~$0.003  | $3.00  |
| **Total**    |          | **≈ $43.50** |

---

## Word categories (1000 total)

| Category | Count |
|---|---|
| Nouns (people, family, body, nature, food, places…) | 554 |
| Verbs | 186 |
| Adjectives (incl. colours) | 95 |
| Adverbs | 70 |
| Prepositions | 27 |
| Pronouns | 25 |
| Numerals | 21 |
| Conjunctions | 16 |
| Interjections | 6 |
