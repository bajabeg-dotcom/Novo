"""Ulazna tacka za `python -m pa800_enhancer`.

Ocekivane korisnicke greske (nepostojeca datoteka, neispravan SMF, lose
napisan JSON) prijavljuju se kao kratka poruka i izlazni kod, a ne kao
Python traceback. Neocekivane greske i dalje idu punim tracebackom -- one
su bug i ne smiju se sakriti.

Postavi PA800_ENHANCER_TRACEBACK=1 da vidis puni traceback i za obradjene
greske (korisno pri debugiranju).
"""

from __future__ import annotations

import json
import os
import sys

from .cli import main
from .smf.errors import SmfError

# Greske koje su normalan ishod korisnickog unosa, ne kvar programa.
EXPECTED_ERRORS: tuple[type[BaseException], ...] = (
    SmfError,
    OSError,
    ValueError,
    json.JSONDecodeError,
)

EXIT_USAGE_ERROR = 2


def _run() -> int:
    if os.environ.get("PA800_ENHANCER_TRACEBACK") == "1":
        return main()
    try:
        return main()
    except KeyboardInterrupt:
        print("prekinuto", file=sys.stderr)
        return 130
    except EXPECTED_ERRORS as error:
        name = type(error).__name__
        print(f"error: {error} ({name})", file=sys.stderr)
        return EXIT_USAGE_ERROR


if __name__ == "__main__":
    raise SystemExit(_run())
