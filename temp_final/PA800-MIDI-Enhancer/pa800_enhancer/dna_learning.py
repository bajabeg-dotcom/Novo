from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .corpus import CorpusRunner
from .database import DEFAULT_DATABASE_PATH, LocalDatabase
from .dna import extract_fingerprint


@dataclass(frozen=True, slots=True)
class DnaLearningResult:
    scanned: int
    imported: int
    failed: int
    gold: int
    factory: int
    failures: tuple[str, ...]


class DnaLearner:
    def __init__(self, corpus: CorpusRunner | None = None, database: LocalDatabase | None = None) -> None:
        self.corpus = corpus or CorpusRunner()
        self.database = database or LocalDatabase()

    def learn(
        self,
        sources: tuple[Path, ...],
        *,
        database_path: Path = DEFAULT_DATABASE_PATH,
        gold_match: str = "Gold DNA.zip",
        factory_match: str = "Split Factory Styles.zip",
        force: bool = False,
    ) -> DnaLearningResult:
        scanned = imported = gold = factory = 0
        failures: list[str] = []
        existing_index = self.database.fingerprint_index(database_path)
        source_links: list[tuple[str, str, str, str]] = []
        gold_token, factory_token = gold_match.casefold(), factory_match.casefold()
        for locator, data in self.corpus.iter_midi(sources):
            folded = locator.casefold()
            kind = "gold" if gold_token in folded else "factory" if factory_token in folded else None
            if kind is None:
                continue
            scanned += 1
            try:
                source_sha256 = hashlib.sha256(data).hexdigest()
                existing = existing_index.get((source_sha256, kind))
                if existing and not force:
                    source_links.append((locator, kind, source_sha256, existing))
                    imported += 1
                    gold += kind == "gold"
                    factory += kind == "factory"
                    continue
                song = self.corpus.reader.parse(data)
                fingerprint = extract_fingerprint(song)
                self.database.import_fingerprint(fingerprint, locator, kind, database_path)
                existing_index[(source_sha256, kind)] = fingerprint.fingerprint_id
                imported += 1
                gold += kind == "gold"
                factory += kind == "factory"
            except (OSError, RuntimeError, ValueError) as error:
                failures.append(f"{locator}: {error}")
        self.database.link_fingerprint_sources(source_links, database_path)
        return DnaLearningResult(scanned, imported, len(failures), gold, factory, tuple(failures))
