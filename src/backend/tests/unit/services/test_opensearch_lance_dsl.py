from langflow.services.knowledge.opensearch_lance.dsl import build_predicate_from_bool, extract_knn


def test_build_predicate_simple_term():
    bool_node = {"must": [{"term": {"author": "alice"}}]}
    pred = build_predicate_from_bool(bool_node)
    assert pred == "author == 'alice'"


def test_build_predicate_terms_and_range():
    bool_node = {
        "filter": [
            {"terms": {"tag": ["a", "b"]}},
            {"range": {"year": {"gte": 2020}}},
        ]
    }
    pred = build_predicate_from_bool(bool_node)
    assert pred is not None
    assert "(tag == 'a' OR tag == 'b')" in pred
    assert "year >= 2020" in pred


def test_build_predicate_should_or_join():
    bool_node = {
        "should": [
            {"term": {"category": "news"}},
            {"term": {"category": "blog"}},
        ]
    }
    pred = build_predicate_from_bool(bool_node)
    assert pred.startswith("(") and pred.endswith(")")
    assert "category == 'news' OR category == 'blog'" in pred


def test_build_predicate_must_and_filter_combined():
    bool_node = {
        "must": [{"term": {"author": "alice"}}],
        "filter": [{"range": {"likes": {"gte": 10}}}],
    }
    pred = build_predicate_from_bool(bool_node)
    assert pred == "author == 'alice' AND likes >= 10"


def test_build_predicate_match_treated_as_term():
    bool_node = {"must": [{"match": {"title": "hello"}}]}
    pred = build_predicate_from_bool(bool_node)
    assert pred == "title == 'hello'"


def test_build_predicate_empty_bool_returns_none():
    pred = build_predicate_from_bool({})
    assert pred is None


def test_build_predicate_exists_and_must_not():
    bool_node = {
        "filter": [{"exists": {"field": "author"}}],
        "must_not": [{"exists": {"field": "deleted_at"}}],
    }
    pred = build_predicate_from_bool(bool_node)
    assert "EXISTS(author)" in (pred or "")
    assert "NOT (EXISTS(deleted_at))" in (pred or "")


def test_extract_knn_with_defaults():
    body = {"knn": {"query_vector": [0.1, 0.2, 0.3], "k": 5}}
    field, vector, k = extract_knn(body)  # type: ignore[misc]
    assert field == "vector"
    assert vector == [0.1, 0.2, 0.3]
    assert k == 5


def test_extract_knn_alt_queryVector_and_size_from_body():
    body = {"size": 7, "knn": {"field": "embedding", "queryVector": [1.0, 2.0, 3.0]}}
    field, vector, k = extract_knn(body)  # type: ignore[misc]
    assert field == "embedding"
    assert vector == [1.0, 2.0, 3.0]
    assert k == 7
