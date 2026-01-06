"""AI conversation endpoints for interactive training plan generation."""

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.ai_constants import (
    AI_MAX_TOKENS,
    AI_TEMPERATURE,
    RUNNING_COACH_PLAN_PROMPT,
    RUNNING_COACH_SYSTEM_PROMPT,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.models.ai import AIConversation, AIImport, AIMessage
from app.models.user import User
from app.observability import get_metrics_backend

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class MessageCreate(BaseModel):
    """Request to send a message to AI."""

    content: str


class MessageResponse(BaseModel):
    """AI message response."""

    id: int
    role: str
    content: str
    token_count: int | None = None  # DB column is 'token_count'
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation response."""

    id: int
    title: str | None
    context_type: str | None = None  # DB: context_type (not language)
    context_data: dict[str, Any] | None = None  # DB: context_data (not model)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Conversation with paginated messages."""

    id: int
    title: str | None
    context_type: str | None = None
    context_data: dict[str, Any] | None = None
    messages: list[MessageResponse]
    total_messages: int
    has_more: bool
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Paginated conversation list."""

    items: list[ConversationResponse]
    total: int


class ChatRequest(BaseModel):
    """Request to chat with AI."""

    message: str
    context: dict[str, Any] | None = None
    mode: Literal["chat", "plan"] | None = None
    save_mode: Literal["draft", "approved", "active"] | None = None


class ChatResponse(BaseModel):
    """AI chat response."""

    conversation_id: int
    message: MessageResponse
    reply: MessageResponse
    plan_id: int | None = None
    import_id: int | None = None
    plan_status: str | None = None
    missing_fields: list[str] | None = None


# -------------------------------------------------------------------------
# Import/Export Models
# -------------------------------------------------------------------------


class WorkoutStepSchema(BaseModel):
    """Single workout step (warmup, main, cooldown, etc.)."""

    type: str  # warmup, main, cooldown, rest, recovery
    duration_minutes: int | None = None
    distance_km: float | None = None
    target_pace: str | None = None  # e.g., "5:30-5:45"
    target_hr_zone: int | None = None  # 1-5
    description: str | None = None


class WorkoutSchema(BaseModel):
    """Single workout definition."""

    name: str
    type: str  # easy, long, tempo, interval, hills, fartlek, rest
    steps: list[WorkoutStepSchema]
    notes: str | None = None


class PlanWeekSchema(BaseModel):
    """Single week in the training plan."""

    week_number: int
    focus: str  # build, recovery, taper, race
    workouts: list[WorkoutSchema]
    weekly_distance_km: float | None = None
    notes: str | None = None


class PlanImportRequest(BaseModel):
    """Request to import a training plan from external source.

    Date calculation rules:
    1. start_date provided: use as-is
    2. start_date not provided + goal_date provided: start_date = goal_date - (weeks * 7 days)
    3. Neither provided: start_date = today, end_date = today + (weeks * 7 days)
    """

    source: str = "manual"  # manual, chatgpt, other
    plan_name: str
    goal_type: str  # marathon, half, 10k, 5k, fitness
    start_date: str | None = None  # ISO date string (optional)
    goal_date: str | None = None  # ISO date string (race day / plan end)
    goal_time: str | None = None  # e.g., "3:30:00"
    weeks: list[PlanWeekSchema]
    notes: str | None = None


class PlanImportResponse(BaseModel):
    """Response after importing a plan."""

    import_id: int
    plan_id: int
    weeks_created: int
    workouts_created: int
    message: str


class ExportSummaryResponse(BaseModel):
    """ChatGPT analysis summary for export."""

    format: str  # markdown, json
    content: str
    generated_at: datetime


# -------------------------------------------------------------------------
# Conversation Endpoints
# -------------------------------------------------------------------------


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ConversationListResponse:
    """List AI conversations for the current user.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.

    Returns:
        Paginated list of conversations.
    """
    # Count total
    count_query = select(func.count(AIConversation.id)).where(
        AIConversation.user_id == current_user.id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get page
    offset = (page - 1) * per_page
    query = (
        select(AIConversation)
        .where(AIConversation.user_id == current_user.id)
        .order_by(AIConversation.updated_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()

    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
    )


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    title: Optional[str] = None
    language: str | None = None  # Uses AI_DEFAULT_LANGUAGE from config if not set


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    request: CreateConversationRequest | None = None,
) -> ConversationResponse:
    """Create a new AI conversation.

    Accepts either JSON body or empty request (uses defaults).

    Args:
        current_user: Authenticated user.
        db: Database session.
        request: Optional request body with title and language.

    Returns:
        Created conversation.
    """
    title = request.title if request else None
    language = (request.language if request and request.language else None) or settings.ai_default_language

    conversation = AIConversation(
        user_id=current_user.id,
        title=title or "새 대화",
        language=language,
        model=settings.openai_model,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Max messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
) -> ConversationDetailResponse:
    """Get conversation with paginated messages.

    Messages are returned in ascending order by creation time (oldest first).
    Use limit/offset for pagination when conversations have many messages.

    Args:
        conversation_id: Conversation ID.
        current_user: Authenticated user.
        db: Database session.
        limit: Maximum number of messages to return (1-100, default 50).
        offset: Number of messages to skip for pagination.

    Returns:
        Conversation with paginated messages.

    Raises:
        HTTPException: If not found.
    """
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get total message count
    count_result = await db.execute(
        select(func.count(AIMessage.id))
        .where(AIMessage.conversation_id == conversation_id)
    )
    total_messages = count_result.scalar() or 0

    # Get paginated messages
    msg_result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = msg_result.scalars().all()

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        context_type=conversation.context_type,
        context_data=conversation.context_data,
        messages=[MessageResponse.model_validate(m) for m in messages],
        total_messages=total_messages,
        has_more=(offset + len(messages)) < total_messages,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation.

    Args:
        conversation_id: Conversation ID.
        current_user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException: If not found.
    """
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    await db.delete(conversation)
    await db.commit()


# -------------------------------------------------------------------------
# Chat Endpoint
# -------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/chat", response_model=ChatResponse)
async def chat(
    conversation_id: int,
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message to AI and get a response.

    Args:
        conversation_id: Conversation ID.
        request: Chat request with message.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        User message and AI reply.

    Raises:
        HTTPException: If conversation not found or AI error.
    """
    # Verify conversation ownership
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get AI response first (before saving user message to avoid duplication in history)
    plan_id = None
    import_id = None
    plan_status = None
    missing_fields = None

    try:
        if request.mode == "plan":
            ai_response = await _get_ai_plan_response(
                conversation=conversation,
                user_message=request.message,
                context=request.context,
                db=db,
            )
        else:
            ai_response = await _get_ai_response(
                conversation=conversation,
                user_message=request.message,
                context=request.context,
                db=db,
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("AI service error in conversation chat")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable. Please try again.",
        )

    assistant_content = ai_response["content"]

    if request.mode == "plan":
        payload = ai_response.get("payload") or {}
        response_status = payload.get("status")
        assistant_content = payload.get("assistant_message") or "플랜 생성을 계속 진행합니다."

        if response_status == "plan":
            plan_data = payload.get("plan")
            if not isinstance(plan_data, dict):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI plan response missing plan data",
                )
            plan_data["source"] = "ai"
            # Validate AI-generated plan JSON against schema
            try:
                from pydantic import ValidationError as PydanticValidationError
                plan_request = PlanImportRequest.model_validate(plan_data)
            except PydanticValidationError as e:
                logger.warning(f"AI generated invalid plan JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI generated plan with invalid format: {e.error_count()} validation errors. Please try again.",
                )
            import_result = await import_plan(plan_request, current_user, db)
            plan_id = import_result.plan_id
            import_id = import_result.import_id
            plan_status = "draft"

            save_mode = request.save_mode or "draft"
            if save_mode in ("approved", "active"):
                from app.api.v1.endpoints.plans import approve_plan, activate_plan

                await approve_plan(plan_id, current_user, db)
                plan_status = "approved"
                if save_mode == "active":
                    await activate_plan(plan_id, current_user, db)
                    plan_status = "active"
        elif response_status == "need_info":
            missing_fields = payload.get("missing_fields") or []
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid AI plan response format",
            )

    # Save user message (after AI response to avoid duplication)
    user_message = AIMessage(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)

    # Save AI response
    assistant_message = AIMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_count=ai_response.get("tokens"),
    )
    db.add(assistant_message)

    # Update conversation timestamp
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()

    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation_id,
        message=MessageResponse.model_validate(user_message),
        reply=MessageResponse.model_validate(assistant_message),
        plan_id=plan_id,
        import_id=import_id,
        plan_status=plan_status,
        missing_fields=missing_fields,
    )


# -------------------------------------------------------------------------
# Quick Chat Endpoint (creates conversation automatically)
# -------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def quick_chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Quick chat - creates a new conversation and sends a message.

    Args:
        request: Chat request with message.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        User message and AI reply with new conversation ID.
    """
    # Create new conversation
    # DB schema uses context_type and context_data instead of language/model
    conversation = AIConversation(
        user_id=current_user.id,
        title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
        context_type="plan_generation" if request.mode == "plan" else "chat",
        context_data={
            "language": settings.ai_default_language,
            "model": settings.openai_model,
            "mode": request.mode,
        },
    )
    db.add(conversation)
    await db.flush()  # Need conversation.id for messages

    # Get AI response first (before saving user message to avoid duplication in history)
    plan_id = None
    import_id = None
    plan_status = None
    missing_fields = None

    try:
        if request.mode == "plan":
            ai_response = await _get_ai_plan_response(
                conversation=conversation,
                user_message=request.message,
                context=request.context,
                db=db,
            )
        else:
            ai_response = await _get_ai_response(
                conversation=conversation,
                user_message=request.message,
                context=request.context,
                db=db,
            )
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        logger.exception("AI service error in quick chat")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable. Please try again.",
        )

    assistant_content = ai_response["content"]

    if request.mode == "plan":
        payload = ai_response.get("payload") or {}
        response_status = payload.get("status")
        assistant_content = payload.get("assistant_message") or "플랜 생성을 계속 진행합니다."

        if response_status == "plan":
            plan_data = payload.get("plan")
            if not isinstance(plan_data, dict):
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI plan response missing plan data",
                )
            plan_data["source"] = "ai"
            # Validate AI-generated plan JSON against schema
            try:
                from pydantic import ValidationError as PydanticValidationError
                plan_request = PlanImportRequest.model_validate(plan_data)
            except PydanticValidationError as e:
                await db.rollback()
                logger.warning(f"AI generated invalid plan JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI generated plan with invalid format: {e.error_count()} validation errors. Please try again.",
                )
            import_result = await import_plan(plan_request, current_user, db)
            plan_id = import_result.plan_id
            import_id = import_result.import_id
            plan_status = "draft"

            save_mode = request.save_mode or "draft"
            if save_mode in ("approved", "active"):
                from app.api.v1.endpoints.plans import approve_plan, activate_plan

                await approve_plan(plan_id, current_user, db)
                plan_status = "approved"
                if save_mode == "active":
                    await activate_plan(plan_id, current_user, db)
                    plan_status = "active"
        elif response_status == "need_info":
            missing_fields = payload.get("missing_fields") or []
        else:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid AI plan response format",
            )

    # Save user message (after AI response to avoid duplication)
    user_message = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)

    # Save AI response
    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_content,
        token_count=ai_response.get("tokens"),
    )
    db.add(assistant_message)

    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        message=MessageResponse.model_validate(user_message),
        reply=MessageResponse.model_validate(assistant_message),
        plan_id=plan_id,
        import_id=import_id,
        plan_status=plan_status,
        missing_fields=missing_fields,
    )


# -------------------------------------------------------------------------
# Internal AI Service
# -------------------------------------------------------------------------


def _extract_json_payload(content: str) -> dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in AI response")
    return json.loads(content[start : end + 1])


async def _get_rag_context(query: str) -> str:
    """Search knowledge base and return formatted context.

    Args:
        query: User's question/message.

    Returns:
        Formatted context string, or empty string if no results.
    """
    try:
        from app.knowledge.retriever import get_knowledge_retriever

        retriever = get_knowledge_retriever()
        if retriever is None or not retriever.is_initialized:
            return ""

        results = await retriever.search(
            query=query,
            top_k=settings.rag_top_k,
            min_score=settings.rag_min_score,
        )

        if not results:
            return ""

        return retriever.format_context(
            results,
            max_length=settings.rag_max_context_length,
        )
    except Exception as e:
        logger.warning(f"RAG search failed: {e}")
        return ""


async def _get_ai_response(
    conversation: AIConversation,
    user_message: str,
    context: dict[str, Any] | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Get AI response using Google Gemini or OpenAI API.

    Args:
        conversation: Current conversation.
        user_message: User's message.
        context: Optional context (training data, goals, etc.).
        db: Database session.

    Returns:
        Dict with content and token count.
    """
    metrics = get_metrics_backend()

    # Build message history (get most recent N messages, ordered chronologically)
    history_limit = settings.ai_max_history_messages
    msg_result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation.id)
        .order_by(AIMessage.created_at.desc())
        .limit(history_limit)
    )
    history_raw = list(reversed(msg_result.scalars().all()))

    # Deduplicate consecutive messages with same role and content
    history: list = []
    for msg in history_raw:
        if history and history[-1].role == msg.role and history[-1].content == msg.content:
            continue
        history.append(msg)

    # RAG: Search knowledge base for relevant context
    system_prompt = RUNNING_COACH_SYSTEM_PROMPT
    if settings.rag_enabled:
        rag_context = await _get_rag_context(user_message)
        if rag_context:
            system_prompt = f"{RUNNING_COACH_SYSTEM_PROMPT}\n\n[참고 자료]\n{rag_context}"

    # Use Google Gemini or OpenAI based on settings
    if settings.ai_provider == "google" and settings.google_ai_api_key:
        return await _get_gemini_response(
            history=history,
            user_message=user_message,
            context=context,
            system_prompt=system_prompt,
            metrics=metrics,
        )
    else:
        return await _get_openai_response(
            history=history,
            user_message=user_message,
            context=context,
            system_prompt=system_prompt,
            metrics=metrics,
        )


async def _get_gemini_response(
    history: list,
    user_message: str,
    context: dict[str, Any] | None,
    system_prompt: str,
    metrics,
) -> dict[str, Any]:
    """Get AI response using Google Gemini API."""
    import google.generativeai as genai

    genai.configure(api_key=settings.google_ai_api_key)
    model = genai.GenerativeModel(
        model_name=settings.google_ai_model,
        system_instruction=system_prompt,
    )

    # Build chat history for Gemini
    gemini_history = []
    for msg in history:
        role = "user" if msg.role == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg.content]})

    # Add context to user message if provided
    full_message = user_message
    if context:
        full_message = f"[사용자 컨텍스트: {context}]\n\n{user_message}"

    start_time = time.perf_counter()
    status_code = 500
    try:
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(full_message)
        status_code = 200
    except Exception:
        status_code = 500
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.observe_external_api("google", "gemini.chat", status_code, duration_ms)
        logger.info(
            "Google Gemini API chat status=%s duration_ms=%.2f model=%s",
            status_code,
            duration_ms,
            settings.google_ai_model,
        )

    # Get token count from usage metadata if available
    tokens = None
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        tokens = response.usage_metadata.total_token_count

    return {
        "content": response.text,
        "tokens": tokens,
    }


async def _get_openai_response(
    history: list,
    user_message: str,
    context: dict[str, Any] | None,
    system_prompt: str,
    metrics,
) -> dict[str, Any]:
    """Get AI response using OpenAI API (fallback)."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    messages = [{"role": "system", "content": system_prompt}]

    if context:
        context_str = f"[사용자 컨텍스트: {context}]"
        messages.append({"role": "system", "content": context_str})

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_message})

    start_time = time.perf_counter()
    status_code = 500
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=AI_MAX_TOKENS,
            temperature=AI_TEMPERATURE,
        )
        status_code = 200
    except Exception:
        status_code = 500
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.observe_external_api("openai", "chat.completions", status_code, duration_ms)
        logger.info(
            "OpenAI API chat.completions status=%s duration_ms=%.2f",
            status_code,
            duration_ms,
        )

    return {
        "content": response.choices[0].message.content,
        "tokens": response.usage.total_tokens if response.usage else None,
    }


async def _get_ai_plan_response(
    conversation: AIConversation,
    user_message: str,
    context: dict[str, Any] | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Get AI plan response in JSON format using Google Gemini or OpenAI."""
    metrics = get_metrics_backend()

    history_limit = settings.ai_max_history_messages
    msg_result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation.id)
        .order_by(AIMessage.created_at.desc())
        .limit(history_limit)
    )
    history_raw = list(reversed(msg_result.scalars().all()))

    history: list = []
    for msg in history_raw:
        if history and history[-1].role == msg.role and history[-1].content == msg.content:
            continue
        history.append(msg)

    # Use Google Gemini or OpenAI based on settings
    if settings.ai_provider == "google" and settings.google_ai_api_key:
        response_data = await _get_gemini_response(
            history=history,
            user_message=user_message,
            context=context,
            system_prompt=RUNNING_COACH_PLAN_PROMPT,
            metrics=metrics,
        )
    else:
        response_data = await _get_openai_response(
            history=history,
            user_message=user_message,
            context=context,
            system_prompt=RUNNING_COACH_PLAN_PROMPT,
            metrics=metrics,
        )

    content = response_data["content"] or ""
    try:
        payload = _extract_json_payload(content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI plan response is not valid JSON",
        ) from exc

    return {
        "content": content,
        "payload": payload,
        "tokens": response_data.get("tokens"),
    }


# -------------------------------------------------------------------------
# Import/Export Endpoints
# -------------------------------------------------------------------------


@router.post("/import", response_model=PlanImportResponse, status_code=status.HTTP_201_CREATED)
async def import_plan(
    request: PlanImportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanImportResponse:
    """Import a training plan from external source (e.g., ChatGPT).

    FR-036: 수동 플랜 import - JSON 스키마 검증, import 로그 저장, 실패 시 상세 오류 반환

    Args:
        request: Plan import request with weeks and workouts.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Import result with created plan and workout counts.

    Raises:
        HTTPException: If validation fails or import error occurs.
    """
    from app.models.plan import Plan, PlanWeek
    from app.models.workout import Workout

    try:
        # Validate weeks structure
        if not request.weeks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plan must have at least one week",
            )

        # Parse start_date if provided
        start_date_parsed = None
        if request.start_date:
            try:
                start_date_parsed = date.fromisoformat(request.start_date.split("T")[0])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid start_date format: {request.start_date}",
                )

        # Parse goal date if provided
        goal_date_parsed = None
        if request.goal_date:
            try:
                goal_date_parsed = date.fromisoformat(request.goal_date.split("T")[0])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid goal_date format: {request.goal_date}",
                )

        # Calculate plan start_date and end_date
        # Rules:
        # 1. start_date provided: use as-is
        # 2. start_date not provided + goal_date provided: start_date = goal_date - (weeks * 7 - 1) days
        # 3. Neither provided: start_date = today, end_date = today + (weeks * 7 - 1) days
        #
        # NOTE: end_date is INCLUSIVE. For N weeks:
        #   - Week 1: day 1-7, Week 2: day 8-14, ..., Week N: day (N-1)*7+1 to N*7
        #   - end_date = start_date + (N * 7 - 1) days
        num_weeks = len(request.weeks)
        plan_duration_days = num_weeks * 7 - 1  # Inclusive: last day of last week

        if start_date_parsed:
            plan_start_date = start_date_parsed
            plan_end_date = goal_date_parsed if goal_date_parsed else (plan_start_date + timedelta(days=plan_duration_days))
        elif goal_date_parsed:
            # Backtrack from goal date (goal_date = end_date)
            plan_end_date = goal_date_parsed
            plan_start_date = goal_date_parsed - timedelta(days=plan_duration_days)
        else:
            # Default: start today
            plan_start_date = date.today()
            plan_end_date = plan_start_date + timedelta(days=plan_duration_days)

        # Validate: goal_date should not be before start_date
        if goal_date_parsed and goal_date_parsed < plan_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"goal_date ({goal_date_parsed}) cannot be before start_date ({plan_start_date})",
            )

        # Create plan (map request fields to model fields)
        plan = Plan(
            user_id=current_user.id,
            goal_type=request.goal_type,
            goal_date=goal_date_parsed,
            goal_time=request.goal_time,
            start_date=plan_start_date,
            end_date=plan_end_date,
            status="draft",
            description=f"{request.plan_name}\n\n{request.notes or ''}".strip(),
        )
        db.add(plan)
        await db.flush()

        # Create weeks and workouts
        weeks_created = 0
        workouts_created = 0

        for week_data in request.weeks:
            # Map request fields to model fields
            plan_week = PlanWeek(
                plan_id=plan.id,
                week_index=week_data.week_number,  # week_number -> week_index
                focus=week_data.focus,
                target_distance_km=week_data.weekly_distance_km,  # weekly_distance_km -> target_distance_km
                notes=week_data.notes,
            )
            db.add(plan_week)
            await db.flush()
            weeks_created += 1

            for workout_data in week_data.workouts:
                # Map request fields to model fields
                # Note: structure should be list of step dicts (not wrapped in {"steps": ...})
                # Notes go to dedicated notes field (not target)
                workout = Workout(
                    plan_week_id=plan_week.id,
                    user_id=current_user.id,
                    name=workout_data.name,
                    workout_type=workout_data.type,  # type -> workout_type
                    structure=[step.model_dump() for step in workout_data.steps],
                    notes=workout_data.notes,  # Use dedicated notes field
                )
                db.add(workout)
                workouts_created += 1

        # Log import with DB schema fields
        ai_import = AIImport(
            user_id=current_user.id,
            source=request.source,
            import_type="plan",  # DB requires import_type
            raw_content=json.dumps(request.model_dump(), ensure_ascii=False),  # Original input
            parsed_data=request.model_dump(),  # Validated payload
            status="success",  # Import succeeded
            result_plan_id=plan.id,  # Link to created plan
            processed_at=datetime.now(timezone.utc),
        )
        db.add(ai_import)
        await db.flush()

        await db.commit()
        await db.refresh(ai_import)

        return PlanImportResponse(
            import_id=ai_import.id,
            plan_id=plan.id,
            weeks_created=weeks_created,
            workouts_created=workouts_created,
            message=f"Successfully imported plan '{request.plan_name}' with {weeks_created} weeks and {workouts_created} workouts",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Plan import failed")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import failed. Please check the plan format and try again.",
        )


@router.get("/export", response_model=ExportSummaryResponse)
async def export_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    include_sensitive: bool = Query(False, description="Include potentially sensitive data"),
) -> ExportSummaryResponse:
    """Generate training summary for ChatGPT analysis.

    FR-037: ChatGPT 분석용 요약/복사 - Markdown/JSON 포맷, 최근 6주 + 12주 추세 + 전체 이력 요약

    Args:
        current_user: Authenticated user.
        db: Database session.
        format: Output format (markdown or json).
        include_sensitive: Whether to include sensitive data.

    Returns:
        Summary content for ChatGPT analysis.
    """
    import json
    from datetime import timedelta

    from app.models.activity import Activity
    from app.models.health import FitnessMetricDaily

    now = datetime.now(timezone.utc)
    six_weeks_ago = now - timedelta(weeks=6)
    twelve_weeks_ago = now - timedelta(weeks=12)

    # Get recent activities (6 weeks)
    recent_result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == current_user.id,
            Activity.start_time >= six_weeks_ago,
        )
        .order_by(Activity.start_time.desc())
    )
    recent_activities = recent_result.scalars().all()

    # Get 12-week activities for trend
    trend_result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == current_user.id,
            Activity.start_time >= twelve_weeks_ago,
        )
        .order_by(Activity.start_time.desc())
    )
    trend_activities = trend_result.scalars().all()

    # Get all-time stats
    all_time_result = await db.execute(
        select(
            func.count(Activity.id).label("total_count"),
            func.sum(Activity.distance_meters).label("total_distance"),
            func.sum(Activity.duration_seconds).label("total_duration"),
        ).where(Activity.user_id == current_user.id)
    )
    all_time = all_time_result.one()

    # Get recent fitness metrics
    fitness_result = await db.execute(
        select(FitnessMetricDaily)
        .where(
            FitnessMetricDaily.user_id == current_user.id,
            FitnessMetricDaily.date >= six_weeks_ago.date(),
        )
        .order_by(FitnessMetricDaily.date.desc())
        .limit(7)
    )
    recent_fitness = fitness_result.scalars().all()

    # Build summary data
    summary_data = {
        "profile": {
            "display_name": current_user.display_name if include_sensitive else "Runner",
            "timezone": current_user.timezone or settings.default_timezone,
        },
        "recent_6_weeks": {
            "total_activities": len(recent_activities),
            "total_distance_km": round(sum(a.distance_meters or 0 for a in recent_activities) / 1000, 1),
            "total_duration_hours": round(sum(a.duration_seconds or 0 for a in recent_activities) / 3600, 1),
            "avg_pace_per_km": _calculate_avg_pace(recent_activities),
            "avg_hr": _calculate_avg_hr(recent_activities),
        },
        "trend_12_weeks": {
            "total_activities": len(trend_activities),
            "total_distance_km": round(sum(a.distance_meters or 0 for a in trend_activities) / 1000, 1),
            "weekly_avg_distance_km": round(sum(a.distance_meters or 0 for a in trend_activities) / 1000 / 12, 1),
        },
        "all_time": {
            "total_activities": all_time.total_count or 0,
            "total_distance_km": round((all_time.total_distance or 0) / 1000, 1),
            "total_duration_hours": round((all_time.total_duration or 0) / 3600, 1),
        },
        "fitness_metrics": {
            "latest_ctl": recent_fitness[0].ctl if recent_fitness else None,
            "latest_atl": recent_fitness[0].atl if recent_fitness else None,
            "latest_tsb": recent_fitness[0].tsb if recent_fitness else None,
        } if recent_fitness else None,
    }

    # Format output
    if format == "json":
        content = json.dumps(summary_data, ensure_ascii=False, indent=2)
    else:
        content = _format_markdown_summary(summary_data)

    return ExportSummaryResponse(
        format=format,
        content=content,
        generated_at=now,
    )


def _calculate_avg_pace(activities: list) -> str:
    """Calculate average pace from activities."""
    total_distance = sum(a.distance_meters or 0 for a in activities)
    total_duration = sum(a.duration_seconds or 0 for a in activities)

    if total_distance == 0:
        return "N/A"

    pace_seconds_per_km = (total_duration / total_distance) * 1000
    minutes = int(pace_seconds_per_km // 60)
    seconds = int(pace_seconds_per_km % 60)
    return f"{minutes}:{seconds:02d}/km"


def _calculate_avg_hr(activities: list) -> int | None:
    """Calculate average heart rate from activities with valid HR data.

    Only considers activities that have actual heart rate data (avg_hr > 0).
    Returns None if no activities have valid HR data.
    """
    activities_with_hr = [a for a in activities if a.avg_hr and a.avg_hr > 0]
    if not activities_with_hr:
        return None
    return round(sum(a.avg_hr for a in activities_with_hr) / len(activities_with_hr))


def _format_markdown_summary(data: dict) -> str:
    """Format summary data as markdown."""
    lines = [
        "# 러닝 훈련 데이터 요약",
        "",
        "## PROFILE",
        f"- 이름: {data['profile']['display_name']}",
        f"- 타임존: {data['profile']['timezone']}",
        "",
        "## RECENT 6 WEEKS (최근 6주)",
        f"- 총 활동 수: {data['recent_6_weeks']['total_activities']}회",
        f"- 총 거리: {data['recent_6_weeks']['total_distance_km']}km",
        f"- 총 시간: {data['recent_6_weeks']['total_duration_hours']}시간",
        f"- 평균 페이스: {data['recent_6_weeks']['avg_pace_per_km']}",
        f"- 평균 심박수: {data['recent_6_weeks']['avg_hr']}bpm" if data['recent_6_weeks']['avg_hr'] else "- 평균 심박수: N/A",
        "",
        "## TREND 12 WEEKS (12주 추세)",
        f"- 총 활동 수: {data['trend_12_weeks']['total_activities']}회",
        f"- 총 거리: {data['trend_12_weeks']['total_distance_km']}km",
        f"- 주간 평균 거리: {data['trend_12_weeks']['weekly_avg_distance_km']}km",
        "",
        "## ALL-TIME (전체 이력)",
        f"- 총 활동 수: {data['all_time']['total_activities']}회",
        f"- 총 거리: {data['all_time']['total_distance_km']}km",
        f"- 총 시간: {data['all_time']['total_duration_hours']}시간",
    ]

    if data.get("fitness_metrics"):
        fm = data["fitness_metrics"]
        lines.extend([
            "",
            "## FITNESS METRICS (피트니스 지표)",
            f"- CTL (Chronic Training Load): {fm['latest_ctl']}",
            f"- ATL (Acute Training Load): {fm['latest_atl']}",
            f"- TSB (Training Stress Balance): {fm['latest_tsb']}",
        ])

    lines.extend([
        "",
        "---",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
    ])

    return "\n".join(lines)
