from functools import lru_cache

from opensearchpy import OpenSearch

from settings import settings

SECTIONS_INDEX = "document_sections"

SECTIONS_INDEX_MAPPING = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "document_id": {"type": "integer"},
            "section_id": {"type": "integer"},
            "text": {"type": "text"},
            "locator": {"type": "keyword"},
            "jurisdiction": {"type": "keyword"},
            "court_id": {"type": "integer"},
            "court_level": {"type": "integer"},
            "binding_scope": {"type": "keyword"},
            "date": {"type": "date"},
            "source_type": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 3072,
                "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib"},
            },
        }
    },
}


@lru_cache
def get_client() -> OpenSearch:
    auth = None
    if settings.opensearch_user:
        auth = (settings.opensearch_user, settings.opensearch_password)
    return OpenSearch(hosts=[settings.opensearch_url], http_auth=auth, use_ssl=settings.opensearch_url.startswith("https"))


def ensure_index() -> None:
    client = get_client()
    if not client.indices.exists(index=SECTIONS_INDEX):
        client.indices.create(index=SECTIONS_INDEX, body=SECTIONS_INDEX_MAPPING)
