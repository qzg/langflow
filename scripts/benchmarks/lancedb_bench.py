"""
Minimal benchmarking harness for LanceDB Knowledge backend.

Usage:
  uv run python scripts/benchmarks/lancedb_bench.py

This script creates an index, ingests N items in batches, and runs M queries.
Adjust N, batch size, and k to gauge throughput/latency locally.
"""
from __future__ import annotations

import json
import random
import string
import time

from langflow.services.knowledge.factory import create_knowledge_client


def rand_text(n: int) -> str:
    return " ".join(
        "".join(random.choices(string.ascii_lowercase, k=8)) for _ in range(n)
    )


def main():
    client = create_knowledge_client()
    idx = "bench_kb"
    client.put_index(idx)

    N = 2000
    batch = 200
    start = time.time()
    lines = []
    for i in range(1, N + 1):
        payload = {
            "id": str(i),
            "vector": [random.random() for _ in range(8)],
            "text": rand_text(12),
            "metadata": {"author": "alice" if i % 2 else "bob"},
        }
        lines.append(json.dumps({"index": {"_index": idx, "_id": payload["id"]}}))
        lines.append(json.dumps(payload))
        if len(lines) >= 2 * batch:
            client.bulk(ndjson=lines)
            lines = []
    if lines:
        client.bulk(ndjson=lines)
    ingest_time = time.time() - start

    # query
    qstart = time.time()
    body = {
        "size": 10,
        "knn": {"field": "vector", "query_vector": [0.0] * 8, "k": 10},
        "query": {"bool": {"must": [{"term": {"author": "alice"}}]}},
    }
    client.search(idx, body=body)
    qtime = time.time() - qstart

    print(f"Ingested {N} docs in {ingest_time:.2f}s; one query in {qtime*1000:.1f}ms")


if __name__ == "__main__":
    main()