from langflow.services.knowledge.opensearch_lance.dsl import build_predicate_from_bool


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