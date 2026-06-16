"""Shared normalization helpers.

The goal is to emit JSON whose *string* values match what the Capitol Watch app
already parses (Owner.init / TradeType.init / AmountParser), so the app can swap
to this feed with zero code changes.
"""
import re
import unicodedata

_OWNER = {"sp": "Spouse", "jt": "Joint", "dc": "Dependent Child", "": "Self"}
_TYPE = {"p": "Purchase", "s": "Sale", "e": "Exchange"}

# Drop C0 control chars (except tab/newline/CR) and the Unicode replacement char.
# Built at runtime so no control-byte literal ever lives in this source file.
_DROP = {c: None for c in range(32) if c not in (9, 10, 13)}
_DROP[0xFFFD] = None


def owner_word(code):
    return _OWNER.get((code or "").strip().lower(), "Self")


def type_word(letter, qualifier=None):
    base = _TYPE.get((letter or "").strip().lower(), "Other")
    if qualifier:
        q = "Partial" if "partial" in qualifier.lower() else "Full"
        return f"{base} ({q})"
    return base


def clean_ticker(raw):
    if not raw:
        return None
    t = re.sub(r"[^A-Z0-9.\-]", "", raw.strip().upper())
    if not t or t in ("--", "NA", "NONE") or len(t) > 6:
        return None
    return t


def clean_text(raw, fallback=""):
    """Strip control/replacement chars and collapse whitespace."""
    if not raw:
        return fallback
    text = unicodedata.normalize("NFKC", raw).translate(_DROP)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def clean_amount(raw):
    if not raw:
        return "Undisclosed"
    return re.sub(r"\s+", " ", raw).strip()
