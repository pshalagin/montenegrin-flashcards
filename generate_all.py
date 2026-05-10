#!/usr/bin/env python3
"""
generate_all.py
───────────────
Batch-generates all 1000 flashcards, skipping already-done ones.
Runs cards concurrently (default 3 workers) to respect rate limits
while keeping throughput reasonable.

Usage:
    python3 generate_all.py                   # process all pending
    python3 generate_all.py --workers 5       # faster (higher rate-limit risk)
    python3 generate_all.py --retry-errors    # also redo cards that errored
    python3 generate_all.py --range 1 100     # only cards 0001–0100
    python3 generate_all.py --dry-run         # list what would be done

Estimated time:  ~5–6 hours for 1000 cards at 3 workers
Estimated cost:  ~$43  (DALL-E-3 $40 + GPT $0.5 + TTS $3)

Environment:
    OPENAI_API_KEY   required
"""

import os, sys, argparse, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from generate_card import process_card

CARDS_DIR = Path("cards")


def get_cards(retry_errors: bool, range_: tuple[int, int] | None) -> list[Path]:
    """Return sorted list of card paths that need processing."""
    all_cards = sorted(CARDS_DIR.glob("*.json"))

    if range_:
        lo, hi = range_
        all_cards = [p for p in all_cards if lo <= int(p.stem[:4]) <= hi]

    to_do = []
    for path in all_cards:
        try:
            data = json.loads(path.read_text("utf-8"))
        except Exception:
            to_do.append(path)
            continue

        status = data.get("status", "pending")
        if status == "pending":
            to_do.append(path)
        elif status == "error" and retry_errors:
            to_do.append(path)
        elif status == "generating":
            # previous run was interrupted mid-card — redo
            to_do.append(path)

    return to_do


def print_summary():
    all_cards = sorted(CARDS_DIR.glob("*.json"))
    counts = {"pending": 0, "generating": 0, "done": 0, "error": 0, "other": 0}
    for p in all_cards:
        try:
            s = json.loads(p.read_text("utf-8")).get("status", "other")
            counts[s if s in counts else "other"] += 1
        except Exception:
            counts["other"] += 1

    total = len(all_cards)
    pct = counts["done"] / total * 100 if total else 0
    bar_len = 40
    filled = int(bar_len * counts["done"] / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)

    print(f"\n  [{bar}] {pct:.1f}%")
    print(f"  done={counts['done']}  pending={counts['pending']}  "
          f"error={counts['error']}  total={total}")


def main():
    parser = argparse.ArgumentParser(description="Batch flashcard generator")
    parser.add_argument("--workers",      type=int, default=3,
                        help="Concurrent API calls (default 3)")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Also reprocess cards that previously errored")
    parser.add_argument("--range",        nargs=2, type=int, metavar=("FROM", "TO"),
                        help="Only process card IDs FROM..TO (e.g. --range 1 100)")
    parser.add_argument("--dry-run",      action="store_true",
                        help="List cards to process without calling APIs")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("ERROR: set OPENAI_API_KEY environment variable")

    if not CARDS_DIR.exists():
        sys.exit("ERROR: cards/ directory not found. Run init_stubs.py first.")

    range_ = tuple(args.range) if args.range else None
    to_do = get_cards(retry_errors=args.retry_errors, range_=range_)

    if not to_do:
        print("Nothing to do — all cards are already generated!")
        print_summary()
        return

    print(f"\n{'='*60}")
    print(f"  Montenegrin Flashcard Batch Generator")
    print(f"{'='*60}")
    print(f"  Cards to process : {len(to_do)}")
    print(f"  Workers          : {args.workers}")
    print(f"  Retry errors     : {args.retry_errors}")
    if range_:
        print(f"  Range            : {range_[0]}–{range_[1]}")
    print(f"{'='*60}\n")
    print_summary()

    if args.dry_run:
        print(f"\nDry-run: would process {len(to_do)} cards:")
        for p in to_do[:20]:
            d = json.loads(p.read_text())
            print(f"  {p.stem}  [{d['montenegrin']} → {d['russian']}]")
        if len(to_do) > 20:
            print(f"  … and {len(to_do) - 20} more")
        return

    start = time.time()
    done_count = error_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_card, p): p for p in to_do}

        for future in as_completed(futures):
            path = futures[future]
            try:
                future.result()
                status = json.loads(path.read_text()).get("status")
                if status == "done":
                    done_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                print(f"  ✗ Unhandled exception for {path.name}: {e}")

            # Live progress line
            elapsed = time.time() - start
            total_processed = done_count + error_count
            rate = total_processed / elapsed if elapsed > 0 else 0
            remaining = (len(to_do) - total_processed) / rate if rate > 0 else 0
            print(f"  Progress: {total_processed}/{len(to_do)}  "
                  f"✓{done_count} ✗{error_count}  "
                  f"{rate:.1f}/min  ETA {remaining/60:.0f}min")

    elapsed_total = time.time() - start
    print(f"\n{'='*60}")
    print(f"  Finished in {elapsed_total/60:.1f} min")
    print(f"  Done: {done_count}   Errors: {error_count}")
    print_summary()

    if error_count > 0:
        print(f"\n  ⚠  {error_count} cards failed. Run with --retry-errors to retry them.")


if __name__ == "__main__":
    main()
