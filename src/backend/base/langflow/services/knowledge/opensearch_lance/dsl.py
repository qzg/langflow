from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _normalize_field(field: str) -> str:
    """Map OS field names to LanceDB/SQL identifiers.

    For now assume flat columns. If clients send nested (e.g., metadata.foo),
    keep the dot and let the underlying engine decide (future improvement).
    """
    return field


def _term_expr(field: str, value: Any) -> str:
    if isinstance(value, str):
        return f"{_normalize_field(field)} == '{value}'"
    return f"{_normalize_field(field)} == {value}"


def _range_expr(field: str, ranges: Dict[str, Any]) -> List[str]:
    exprs: List[str] = []
    for op, val in ranges.items():
        if op == "gt":
            exprs.append(f"{_normalize_field(field)} > {val}")
        elif op == "gte":
            exprs.append(f"{_normalize_field(field)} >= {val}")
        elif op == "lt":
            exprs.append(f"{_normalize_field(field)} < {val}")
        elif op == "lte":
            exprs.append(f"{_normalize_field(field)} <= {val}")
    return exprs


def _match_expr(field: str, value: Any) -> str:
    """Basic match semantics mapped to exact equality for now.
    Caller may choose to pre-normalize text at ingestion time.
    """
    return _term_expr(field, value)


def _exists_expr(field: str) -> str:
    return f"EXISTS({_normalize_field(field)})"


def build_predicate_from_bool(bool_node: Dict[str, Any]) -> Optional[str]:
    """Translate a subset of OpenSearch bool query to a simple predicate string.

    Supports must/filter/should with term/terms/range/match. Does not implement
    negation yet. Joins with AND for must/filter and OR for should.
    """
    if not bool_node:
        return None

    clauses: List[str] = []

    def handle_clause(items: Any, joiner: str) -> Optional[str]:
        parts: List[str] = []
        if not items:
            return None
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if "term" in item:
                field, val = next(iter(item["term"].items()))
                parts.append(_term_expr(field, val))
            elif "exists" in item:
                fld = item["exists"].get("field") if isinstance(item["exists"], dict) else item["exists"].get("field")
                if fld:
                    parts.append(_exists_expr(str(fld)))
            elif "terms" in item:
                field, vals = next(iter(item["terms"].items()))
                term_parts = [_term_expr(field, v) for v in vals]
                parts.append("(" + " OR ".join(term_parts) + ")")
            elif "range" in item:
                field, range_dict = next(iter(item["range"].items()))
                parts.extend(_range_expr(field, range_dict))
            elif "match" in item:
                field, val = next(iter(item["match"].items()))
                parts.append(_match_expr(field, val))
        return (" " + joiner + " ").join(parts) if parts else None

    must_expr = handle_clause(bool_node.get("must"), "AND")
    filter_expr = handle_clause(bool_node.get("filter"), "AND")
    should_expr = handle_clause(bool_node.get("should"), "OR")
    # limited must_not support: exists only
    must_not_expr = None
    if bool_node.get("must_not"):
        mn = handle_clause(bool_node.get("must_not"), "OR")
        if mn:
            must_not_expr = f"NOT ({mn})"

    if must_expr:
        clauses.append(must_expr)
    if filter_expr:
        clauses.append(filter_expr)
    if should_expr:
        clauses.append("(" + should_expr + ")")

    if must_not_expr:
        clauses.append(must_not_expr)
    if not clauses:
        return None
    return " AND ".join([c for c in clauses if c])


def extract_knn(body: Dict[str, Any]) -> Optional[Tuple[str, List[float], int]]:
    """Extract (field, vector, k) from a knn query if present."""
    knn = body.get("knn")
    if not knn:
        return None
    field = knn.get("field") or "vector"
    vector = knn.get("query_vector") or knn.get("queryVector")
    k = knn.get("k") or knn.get("size") or body.get("size") or 10
    if isinstance(vector, list) and isinstance(k, int):
        return field, vector, k
    return None