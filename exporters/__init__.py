"""Built-in flashcard exporters and exporter interface."""

from pathlib import Path
from typing import Protocol

from flashcards import Deck

from exporters.achfx import AchfxExporter
from exporters.mochi import MochiExporter


class Exporter(Protocol):
    name: str
    default_output: Path

    def export(self, deck: Deck, output_path: Path, options=None) -> None:
        ...


EXPORTERS: dict[str, Exporter] = {
    AchfxExporter.name: AchfxExporter(),
    MochiExporter.name: MochiExporter(),
}


def get_exporter(name: str) -> Exporter:
    try:
        return EXPORTERS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(EXPORTERS))
        raise ValueError(f"unknown exporter {name!r}; choose one of: {choices}") from exc
