from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import ChunkHit, search_chunks_dense, search_chunks_sparse
from app.retrieval.query_processing import process_query
from app.retrieval.schemas import RetrievedChunk, RetrievalQuery, RetrievalResult


@lru_cache(maxsize=1)
def get_local_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.local_embedding_model)


@dataclass(slots=True)
class HybridRetriever:
    model: SentenceTransformer

    def embed_query(self, query: str) -> list[float]:
        embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding[0].tolist()

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        query_embedding = self.embed_query(query.query)
        processed_query = process_query(query.query)
        dense_hits = search_chunks_dense(query_embedding, top_k=query.dense_k)
        sparse_hits = search_chunks_sparse(processed_query.sparse_query, top_k=query.sparse_k)
        fused_hits = reciprocal_rank_fusion(dense_hits, sparse_hits)[: query.top_k]
        return RetrievalResult(
            query=query.query,
            chunks=[self._to_schema(hit, rank + 1) for rank, hit in enumerate(fused_hits)],
        )

    def _to_schema(self, hit: ChunkHit, fused_rank: int) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            accession_number=hit.accession_number,
            ticker=hit.ticker,
            filing_type=hit.filing_type,
            filing_date=hit.filing_date,
            chunk_index=hit.chunk_index,
            text=hit.text,
            section_title=hit.section_title,
            page_number=hit.page_number,
            fused_rank=fused_rank,
            score=hit.score,
        )
