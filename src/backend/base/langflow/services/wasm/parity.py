from __future__ import annotations


def _normalize_text(s: str) -> str:
    # Lowercase and collapse whitespace for a simple, robust comparison baseline
    return " ".join(s.strip().lower().split())


def compute_text_similarity(a: str, b: str) -> float:
    """Compute a simple similarity score in [0,1] for two text strings.

    Uses difflib.SequenceMatcher ratio over normalized text. Good enough for M0.
    """
    import difflib

    na = _normalize_text(a)
    nb = _normalize_text(b)
    return float(difflib.SequenceMatcher(None, na, nb).ratio())
