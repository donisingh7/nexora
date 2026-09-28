from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_knowledge_query_service
from app.schemas.query import (
    AnswerResponse,
    QueryRequest,
    RetrievalResponse,
)
from app.services.knowledge_query import (
    KnowledgeQueryService,
    LLMConfigurationError,
    retrieved_chunk,
)

router = APIRouter(prefix="/query", tags=["knowledge-query"])


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_knowledge(
    request: QueryRequest,
    service: Annotated[KnowledgeQueryService, Depends(get_knowledge_query_service)],
) -> RetrievalResponse:
    dense, lexical, results = await service.retrieve(
        request.query,
        workspace_id=request.workspace_id,
        top_k=request.top_k,
    )
    return RetrievalResponse(
        workspace_id=request.workspace_id,
        query=request.query,
        dense=[retrieved_chunk(item, index) for index, item in enumerate(dense, 1)],
        lexical=[retrieved_chunk(item, index) for index, item in enumerate(lexical, 1)],
        results=[retrieved_chunk(item, index) for index, item in enumerate(results, 1)],
    )


@router.post("/answer", response_model=AnswerResponse)
async def answer_knowledge(
    request: QueryRequest,
    service: Annotated[KnowledgeQueryService, Depends(get_knowledge_query_service)],
) -> AnswerResponse:
    try:
        return await service.answer(
            request.query,
            workspace_id=request.workspace_id,
            top_k=request.top_k,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
