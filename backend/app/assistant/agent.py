from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from app.config import settings
from app.retrieval.retriever import HybridRetriever
from app.retrieval.schemas import RetrievalQuery, RetrievalResult


@dataclass(slots=True)
class RetrievalDeps:
    retriever: HybridRetriever


def build_retrieval_agent() -> Agent[RetrievalDeps, RetrievalResult]:
    agent = Agent(
        model=settings.gemini_chat_model,
        deps_type=RetrievalDeps,
        result_type=RetrievalResult,
        system_prompt=(
            "You are a retrieval assistant. Use the retrieve_chunks tool to find "
            "relevant source passages and return grounded results."
        ),
    )

    @agent.tool
    def retrieve_chunks(ctx: RunContext[RetrievalDeps], query: str) -> RetrievalResult:
        return ctx.deps.retriever.retrieve(RetrievalQuery(query=query))

    return agent
