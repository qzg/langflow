"""Knowledge backends (OpenSearch-compatible) for Langflow.

This package contains a pluggable interface and concrete implementations
for Knowledge backends that expose an OpenSearch-like surface.

Current targets:
- LanceDB in-process adapter
- (Future) real OpenSearch client wrapper
"""

from .client import OpenSearchCompatClient  # noqa: F401
from .factory import create_knowledge_client  # noqa: F401
