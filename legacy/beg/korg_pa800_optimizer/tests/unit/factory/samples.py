"""Curated real-data sample paths shared by Vertical A's unit tests.

These reference real files already committed under
data/factory/real/** and data/golden/songs/** directly, rather than
duplicating megabytes of real MIDI bytes into tests/fixtures/ -- the
committed corpus is the single source of truth for these bytes.
"""

from __future__ import annotations

from korg_optimizer.infrastructure import config

FACTORY_STYLES_ROOT = config.FACTORY_REAL_ROOT / "Workspace_Styles"

# One real file per Style Element section token.
SECTION_SAMPLES = {
    "Break": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Break.mid",
    "End1": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_End1.mid",
    "End2": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_End2.mid",
    "End3": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_End3.mid",
    "Fill1": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Fill1.mid",
    "Fill2": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Fill2.mid",
    "Intro1": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Intro1.mid",
    "Intro2": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Intro2.mid",
    "Intro3": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Intro3.mid",
    "Var1": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Var1.mid",
    "Var2": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Var2.mid",
    "Var3": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Var3.mid",
    "Var4": FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Var4.mid",
}

# "Clean" file: filename prefix matches its style directory exactly.
CLEAN_SAMPLE = FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Var1.mid"

# Filename/directory mismatch fixtures (docs/DATABASE_ARCHITECTURE.md,
# docs/MIDI_MODEL.md): a style whose true name contains "/" and got
# mangled inconsistently between its directory ("AM ") and filename
# ("AM _ PM_Break.mid"), and a "_3_4_" time-signature-variant qualifier.
MISMATCH_AM_PM = FACTORY_STYLES_ROOT / "AM " / "AM _ PM_Break.mid"
MISMATCH_3_4 = FACTORY_STYLES_ROOT / "Acoustic Bld" / "Acoustic Bld_3_4_Break.mid"

# Spread of track counts, to exercise varying format-1 track structure.
TRACK_COUNT_SAMPLES = {
    4: FACTORY_STYLES_ROOT / "Country 16 Beat" / "Country 16 Beat_Var1.mid",
    8: FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Var1.mid",
    15: FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_Break.mid",
    22: FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_End1.mid",
    50: FACTORY_STYLES_ROOT / "50's  Fox" / "50's  Fox_End3.mid",
}

ALL_FACTORY_SAMPLES = sorted(
    {*SECTION_SAMPLES.values(), MISMATCH_AM_PM, MISMATCH_3_4, *TRACK_COUNT_SAMPLES.values()},
    key=str,
)

# Golden Dataset samples (format 0, full live performances).
GOLDEN_SONGS_ROOT = config.GOLDEN_SONGS_ROOT
GOLDEN_SAMPLE = GOLDEN_SONGS_ROOT / "AL PROLECE-SEMSA UZIVO.MID"
GOLDEN_NEAR_DUPLICATE = GOLDEN_SONGS_ROOT / "BARABA SA SELA-KNINDZA UZIVO (2).MID"
