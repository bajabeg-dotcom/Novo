from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from .analysis.harmony import HarmonyAnalysis
from .analysis.structure import StructureAnalysis
from .database import DEFAULT_DATABASE_PATH, LocalDatabase
from .domain.song import Song


@dataclass(frozen=True, slots=True)
class StoredHarmony:
    source_id: str
    song_id: str
    chord_count: int
    key_label: str | None

@dataclass(frozen=True, slots=True)
class StoredStructure:
    source_id: str; song_id: str; section_count: int; track_segment_count: int


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"


class AnalysisRepository:
    def store_harmony(self, song: Song, analysis: HarmonyAnalysis, *, locator: str,
                      corpus_kind: str="target", path: Path=DEFAULT_DATABASE_PATH) -> StoredHarmony:
        if corpus_kind not in {"gold","factory","target","generated"}: raise ValueError("unsupported corpus kind")
        LocalDatabase().initialize(path)
        source_hash=song.source_sha256
        if not source_hash and song.source_path and song.source_path.is_file():
            source_hash=hashlib.sha256(song.source_path.read_bytes()).hexdigest()
        if not source_hash: raise ValueError("song needs source SHA-256 evidence before persistence")
        source_id=_identifier("source",f"{source_hash}:{locator}"); song_id=_identifier("song",source_id)
        primary=analysis.primary_key
        analysis_json=json.dumps({"key_windows":[{"start_tick":window.start_tick,"end_tick":window.end_tick,"candidates":[asdict(item)|{"label":item.label} for item in window.candidates]} for window in analysis.key_windows]},separators=(",",":"))
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("""INSERT INTO music_sources(source_id,sha256,locator,corpus_kind,evidence_status)
                    VALUES(?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET sha256=excluded.sha256,locator=excluded.locator,corpus_kind=excluded.corpus_kind""",
                    (source_id,source_hash,locator,corpus_kind,"candidate"))
                connection.execute("""INSERT INTO music_songs(song_id,source_id,ppq,end_tick,key_label,key_confidence,analysis_schema,analysis_json)
                    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(song_id) DO UPDATE SET ppq=excluded.ppq,end_tick=excluded.end_tick,key_label=excluded.key_label,key_confidence=excluded.key_confidence,analysis_schema=excluded.analysis_schema,analysis_json=excluded.analysis_json""",
                    (song_id,source_id,song.header.ppq,song.end_tick,primary.label if primary else None,primary.probability if primary else None,1,analysis_json))
                connection.execute("DELETE FROM music_chords WHERE song_id=?",(song_id,))
                connection.executemany("""INSERT INTO music_chords(chord_id,song_id,start_tick,end_tick,root_pitch_class,quality,bass_pitch_class,confidence,evidence_json)
                    VALUES(?,?,?,?,?,?,?,?,?)""",[
                    (_identifier("chord",f"{song_id}:{item.start_tick}:{item.end_tick}"),song_id,item.start_tick,item.end_tick,item.root,item.quality,item.bass,item.confidence,json.dumps({"label":item.label,"evidence_notes":item.evidence_notes,"inferred":item.inferred},separators=(",",":")))
                    for item in analysis.chords])
        return StoredHarmony(source_id,song_id,len(analysis.chords),primary.label if primary else None)

    def store_structure(self, song: Song, analysis: StructureAnalysis, *, locator: str,
                        corpus_kind: str="target", path: Path=DEFAULT_DATABASE_PATH) -> StoredStructure:
        LocalDatabase().initialize(path); source_hash=song.source_sha256
        if not source_hash and song.source_path and song.source_path.is_file(): source_hash=hashlib.sha256(song.source_path.read_bytes()).hexdigest()
        if not source_hash: raise ValueError("song needs source SHA-256 evidence before persistence")
        source_id=_identifier("source",f"{source_hash}:{locator}"); song_id=_identifier("song",source_id)
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("""INSERT INTO music_sources(source_id,sha256,locator,corpus_kind,evidence_status) VALUES(?,?,?,?,?)
                    ON CONFLICT(source_id) DO UPDATE SET sha256=excluded.sha256,locator=excluded.locator,corpus_kind=excluded.corpus_kind""",(source_id,source_hash,locator,corpus_kind,"candidate"))
                connection.execute("""INSERT INTO music_songs(song_id,source_id,ppq,end_tick,analysis_schema) VALUES(?,?,?,?,?)
                    ON CONFLICT(song_id) DO UPDATE SET ppq=excluded.ppq,end_tick=excluded.end_tick,analysis_schema=MAX(music_songs.analysis_schema,excluded.analysis_schema)""",(song_id,source_id,song.header.ppq,song.end_tick,2))
                connection.execute("DELETE FROM music_sections WHERE song_id=?",(song_id,)); connection.execute("DELETE FROM music_tracks WHERE song_id=?",(song_id,))
                connection.executemany("""INSERT INTO music_sections(section_id,song_id,section_type,start_tick,end_tick,confidence,evidence_json)
                    VALUES(?,?,?,?,?,?,?)""",[(_identifier("section",f"{song_id}:{item.start_tick}:{item.end_tick}"),song_id,item.label,item.start_tick,item.end_tick,item.confidence,json.dumps({"start_bar":item.start_bar,"end_bar":item.end_bar,"density":item.density},separators=(",",":"))) for item in analysis.sections])
                connection.executemany("""INSERT INTO music_tracks(track_segment_id,song_id,track_index,channel,start_tick,end_tick,role,bank_msb,bank_lsb,program,role_confidence,evidence_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",[(_identifier("track",f"{song_id}:{item.track_index}:{item.channel}:{item.start_tick}"),song_id,item.track_index,item.channel,item.start_tick,item.end_tick,item.role,item.bank_msb,item.bank_lsb,item.program,item.confidence,json.dumps({"note_count":item.note_count,"key_range":item.key_range},separators=(",",":"))) for item in analysis.track_roles])
        return StoredStructure(source_id,song_id,len(analysis.sections),len(analysis.track_roles))
