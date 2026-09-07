from dataclasses import dataclass, field

from retrieval.embeddings import embed
from retrieval.opensearch_client import SECTIONS_INDEX, get_client


@dataclass
class MetadataFilter:
    jurisdictions: list[str] = field(default_factory=list)
    court_ids: list[int] = field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    source_types: list[str] = field(default_factory=list)
    doc_types: list[str] = field(default_factory=list)

    def to_opensearch_filters(self) -> list[dict]:
        filters: list[dict] = []
        if self.jurisdictions:
            filters.append({"terms": {"jurisdiction": self.jurisdictions}})
        if self.court_ids:
            filters.append({"terms": {"court_id": self.court_ids}})
        if self.source_types:
            filters.append({"terms": {"source_type": self.source_types}})
        if self.doc_types:
            filters.append({"terms": {"doc_type": self.doc_types}})
        if self.date_from or self.date_to:
            date_range = {}
            if self.date_from:
                date_range["gte"] = self.date_from
            if self.date_to:
                date_range["lte"] = self.date_to
            filters.append({"range": {"date": date_range}})
        return filters


@dataclass
class SectionHit:
    document_id: int
    section_id: int
    text: str
    locator: str | None
    jurisdiction: str | None
    source_type: str | None
    doc_type: str | None
    bm25_score: float
    knn_score: float
    fused_score: float


def _reciprocal_rank_fusion(
    bm25_hits: list[dict], knn_hits: list[dict], k: int = 60
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for rank, hit in enumerate(bm25_hits):
        scores[hit["_id"]] = scores.get(hit["_id"], 0.0) + 1.0 / (k + rank + 1)
    for rank, hit in enumerate(knn_hits):
        scores[hit["_id"]] = scores.get(hit["_id"], 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_search(
    query_text: str,
    filters: MetadataFilter | None = None,
    top_k: int = 25,
) -> list[SectionHit]:
    """Metadata-filtered BM25 + kNN vector search, fused by reciprocal rank fusion.

    This function only returns retrieved sections with their scores and locators —
    agents reason over these structured objects, never over raw prose the LLM invents,
    which is what lets every downstream claim carry an exact source_section_id.
    """
    client = get_client()
    filter_clauses = filters.to_opensearch_filters() if filters else []

    bm25_body = {
        "size": top_k,
        "query": {
            "bool": {
                "must": [{"match": {"text": query_text}}],
                "filter": filter_clauses,
            }
        },
    }
    bm25_response = client.search(index=SECTIONS_INDEX, body=bm25_body)
    bm25_hits = bm25_response["hits"]["hits"]

    query_vector = embed(query_text)
    knn_body = {
        "size": top_k,
        "query": {
            "bool": {
                "must": [{"knn": {"embedding": {"vector": query_vector, "k": top_k}}}],
                "filter": filter_clauses,
            }
        },
    }
    knn_response = client.search(index=SECTIONS_INDEX, body=knn_body)
    knn_hits = knn_response["hits"]["hits"]

    fused_scores = _reciprocal_rank_fusion(bm25_hits, knn_hits)
    hits_by_id = {hit["_id"]: hit for hit in [*bm25_hits, *knn_hits]}
    bm25_by_id = {hit["_id"]: hit["_score"] for hit in bm25_hits}
    knn_by_id = {hit["_id"]: hit["_score"] for hit in knn_hits}

    results = []
    for doc_id, fused_score in sorted(fused_scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]:
        source = hits_by_id[doc_id]["_source"]
        results.append(
            SectionHit(
                document_id=source["document_id"],
                section_id=source["section_id"],
                text=source["text"],
                locator=source.get("locator"),
                jurisdiction=source.get("jurisdiction"),
                source_type=source.get("source_type"),
                doc_type=source.get("doc_type"),
                bm25_score=bm25_by_id.get(doc_id, 0.0),
                knn_score=knn_by_id.get(doc_id, 0.0),
                fused_score=fused_score,
            )
        )
    return results
