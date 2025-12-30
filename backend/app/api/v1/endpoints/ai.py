"""AI conversation endpoints for interactive training plan generation."""

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
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
    tokens: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation response."""

    id: int
    title: str | None
    language: str
    model: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Conversation with messages."""

    id: int
    title: str | None
    language: str
    model: str
    messages: list[MessageResponse]
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


class ChatResponse(BaseModel):
    """AI chat response."""

    conversation_id: int
    message: MessageResponse
    reply: MessageResponse


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
    """Request to import a training plan from external source."""

    source: str = "manual"  # manual, chatgpt, other
    plan_name: str
    goal_type: str  # marathon, half, 10k, 5k, fitness
    goal_date: str | None = None  # ISO date string
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
    language: str = "ko"


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
    language = request.language if request else "ko"

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
) -> ConversationDetailResponse:
    """Get conversation with all messages.

    Args:
        conversation_id: Conversation ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Conversation with messages.

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

    # Get messages
    msg_result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        language=conversation.language,
        model=conversation.model,
        messages=[MessageResponse.model_validate(m) for m in messages],
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

    # Save user message
    user_message = AIMessage(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    # Get AI response
    try:
        ai_response = await _get_ai_response(
            conversation=conversation,
            user_message=request.message,
            context=request.context,
            db=db,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}",
        )

    # Save AI response
    assistant_message = AIMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response["content"],
        tokens=ai_response.get("tokens"),
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
    conversation = AIConversation(
        user_id=current_user.id,
        title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
        language="ko",
        model=settings.openai_model,
    )
    db.add(conversation)
    await db.flush()

    # Save user message
    user_message = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    # Get AI response
    try:
        ai_response = await _get_ai_response(
            conversation=conversation,
            user_message=request.message,
            context=request.context,
            db=db,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}",
        )

    # Save AI response
    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=ai_response["content"],
        tokens=ai_response.get("tokens"),
    )
    db.add(assistant_message)

    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        message=MessageResponse.model_validate(user_message),
        reply=MessageResponse.model_validate(assistant_message),
    )


# -------------------------------------------------------------------------
# Internal AI Service
# -------------------------------------------------------------------------


async def _get_ai_response(
    conversation: AIConversation,
    user_message: str,
    context: dict[str, Any] | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Get AI response using OpenAI API.

    Args:
        conversation: Current conversation.
        user_message: User's message.
        context: Optional context (training data, goals, etc.).
        db: Database session.

    Returns:
        Dict with content and token count.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    metrics = get_metrics_backend()

    # Build message history (get most recent 20 messages, ordered chronologically)
    # Note: user_message is not yet committed, so we won't get duplicates
    msg_result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation.id)
        .order_by(AIMessage.created_at.desc())
        .limit(20)  # Limit context window to most recent
    )
    # Reverse to get chronological order (oldest first)
    history = list(reversed(msg_result.scalars().all()))

    # System prompt for running coach
    system_prompt = """당신은 전문 러닝 코치입니다. 사용자의 훈련 데이터와 목표를 기반으로 과학적이고 개인화된 훈련 계획을 제공합니다.

주요 역할:
1. 사용자의 현재 체력 수준과 목표를 파악합니다
2. 과학적 원리에 기반한 훈련 계획을 제안합니다
3. 부상 예방과 회복을 고려합니다
4. 점진적 과부하 원칙을 적용합니다
5. 개인의 일정과 상황을 고려합니다

응답 시 유의사항:
- 친근하고 동기부여가 되는 톤을 사용합니다
- 복잡한 개념은 쉽게 설명합니다
- 구체적인 수치와 계획을 제시합니다
- 사용자의 질문에 직접적으로 답변합니다"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add context if provided
    if context:
        context_str = f"[사용자 컨텍스트: {context}]"
        messages.append({"role": "system", "content": context_str})

    # Add conversation history
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Call OpenAI API
    start_time = time.perf_counter()
    status_code = 500
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
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
        # start_date: today (or provided start)
        # end_date: goal_date or start_date + (weeks * 7 days)
        plan_start_date = date.today()
        if goal_date_parsed:
            plan_end_date = goal_date_parsed
        else:
            plan_end_date = plan_start_date + timedelta(weeks=len(request.weeks))

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
                workout = Workout(
                    plan_week_id=plan_week.id,
                    user_id=current_user.id,
                    name=workout_data.name,
                    workout_type=workout_data.type,  # type -> workout_type
                    structure={"steps": [step.model_dump() for step in workout_data.steps]},
                    target={"notes": workout_data.notes} if workout_data.notes else None,
                )
                db.add(workout)
                workouts_created += 1

        # Log import
        ai_import = AIImport(
            user_id=current_user.id,
            source=request.source,
            payload=request.model_dump(),
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
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
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
            "timezone": current_user.timezone or "Asia/Seoul",
        },
        "recent_6_weeks": {
            "total_activities": len(recent_activities),
            "total_distance_km": round(sum(a.distance_meters or 0 for a in recent_activities) / 1000, 1),
            "total_duration_hours": round(sum(a.duration_seconds or 0 for a in recent_activities) / 3600, 1),
            "avg_pace_per_km": _calculate_avg_pace(recent_activities),
            "avg_hr": round(sum(a.avg_hr or 0 for a in recent_activities if a.avg_hr) / max(len([a for a in recent_activities if a.avg_hr]), 1)),
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
        f"- 평균 심박수: {data['recent_6_weeks']['avg_hr']}bpm",
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
