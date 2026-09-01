from __future__ import annotations

from fastapi import APIRouter
from app.retrieval.retriever import HybridRetriever, get_local_embedding_model
from app.retrieval.schemas import RetrievalQuery, RetrievalResult

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResult)
async def search(query: RetrievalQuery) -> RetrievalResult:
    retriever = HybridRetriever(
        model=get_local_embedding_model(),
    )
    return retriever.retrieve(query)
