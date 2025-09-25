# LanceDB backend for Knowledge (OpenSearch-compatible)

LanceDB is the default Knowledge backend. It provides an OpenSearch-compatible surface for index/doc ingest and `_search` with `knn` + basic `bool` filters, without running a full OpenSearch cluster.

## Enable/Configure
- knowledge_backend: lancedb (default)
- knowledge_lancedb_path: ./data/lancedb (storage path)

## Supported API subset
- PUT /{index} — create index (table)
- DELETE /{index}
- POST /{index}/_doc[/ {id}] — upsert
- POST /_bulk — NDJSON index/delete
- POST /{index}/_search — `knn` + `bool` (must/filter/should; term/terms/range/match/exists)
  - `knn`: field, query_vector, k (or size)
  - `bool`: limited `must_not` (exists only)

## Query semantics
- term/match: exact equality (normalize if needed at ingestion)
- exists: field present
- ranges: gt/gte/lt/lte on scalar fields
- score mapping: `_score = 1/(1 + distance)`

## Ingestion & Retrieval
- Ingestion: embeddings computed per document text; bulk upsert to LanceDB via the client
- Retrieval: embed query; `knn` search with optional filters; results mapped to Data/DataFrame

## Performance & Tuning
- Batch upserts for throughput
- Adjust `k` and `size` according to expected recall/latency
- Keep metadata fields simple scalars for filter performance

## Limitations
- No analyzers/tokenizer parity, limited aggregations, no scroll/point-in-time
- `match` is equality; add normalization at ingestion for case-insensitive matching