"""Calendar notes endpoints for personal memos."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.calendar_note import CalendarNote
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Note Types
# -------------------------------------------------------------------------

NOTE_TYPES = [
    {"value": "memo", "label": "메모", "icon": "📝"},
    {"value": "injury", "label": "부상", "icon": "🩹"},
    {"value": "event", "label": "이벤트", "icon": "🏃"},
    {"value": "rest", "label": "휴식", "icon": "😴"},
    {"value": "goal", "label": "목표", "icon": "🎯"},
]


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class NoteCreateSchema(BaseModel):
    """Schema for creating/updating a note."""

    date: date
    note_type: str = Field(default="memo", description="Note type: memo, injury, event, rest, goal")
    content: str = Field(..., min_length=1, max_length=1000)
    icon: str | None = Field(None, max_length=10)


class NoteUpdateSchema(BaseModel):
    """Schema for updating a note."""

    note_type: str | None = Field(None, description="Note type: memo, injury, event, rest, goal")
    content: str | None = Field(None, min_length=1, max_length=1000)
    icon: str | None = Field(None, max_length=10)


class NoteResponseSchema(BaseModel):
    """Response schema for a note."""

    id: int
    date: date
    note_type: str
    content: str
    icon: str | None

    model_config = {"from_attributes": True}


class NotesListResponseSchema(BaseModel):
    """Response schema for notes list."""

    notes: list[NoteResponseSchema]


class NoteTypesResponseSchema(BaseModel):
    """Response schema for note types."""

    types: list[dict]


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/types", response_model=NoteTypesResponseSchema)
async def get_note_types():
    """Get available note types."""
    return {"types": NOTE_TYPES}


@router.get("", response_model=NotesListResponseSchema)
async def get_notes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    start_date: date | None = Query(None, description="Start date filter"),
    end_date: date | None = Query(None, description="End date filter"),
    note_type: str | None = Query(None, description="Filter by note type"),
):
    """Get all notes for the current user, optionally filtered by date range."""
    query = select(CalendarNote).where(CalendarNote.user_id == current_user.id)

    if start_date:
        query = query.where(CalendarNote.date >= start_date)
    if end_date:
        query = query.where(CalendarNote.date <= end_date)
    if note_type:
        query = query.where(CalendarNote.note_type == note_type)

    query = query.order_by(CalendarNote.date.desc())

    result = await db.execute(query)
    notes = result.scalars().all()

    return {"notes": notes}


@router.get("/{note_date}", response_model=NoteResponseSchema | None)
async def get_note_by_date(
    note_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get a note for a specific date."""
    query = select(CalendarNote).where(
        CalendarNote.user_id == current_user.id,
        CalendarNote.date == note_date,
    )
    result = await db.execute(query)
    note = result.scalar_one_or_none()

    if not note:
        return None

    return note


@router.post("", response_model=NoteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_or_update_note(
    note_data: NoteCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create or update a note for a specific date (upsert)."""
    # Check if note already exists for this date
    query = select(CalendarNote).where(
        CalendarNote.user_id == current_user.id,
        CalendarNote.date == note_data.date,
    )
    result = await db.execute(query)
    existing_note = result.scalar_one_or_none()

    if existing_note:
        # Update existing note
        existing_note.note_type = note_data.note_type
        existing_note.content = note_data.content
        existing_note.icon = note_data.icon
        await db.commit()
        await db.refresh(existing_note)
        return existing_note
    else:
        # Create new note
        note = CalendarNote(
            user_id=current_user.id,
            date=note_data.date,
            note_type=note_data.note_type,
            content=note_data.content,
            icon=note_data.icon,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return note


@router.patch("/{note_date}", response_model=NoteResponseSchema)
async def update_note(
    note_date: date,
    note_data: NoteUpdateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update an existing note."""
    query = select(CalendarNote).where(
        CalendarNote.user_id == current_user.id,
        CalendarNote.date == note_date,
    )
    result = await db.execute(query)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found for this date",
        )

    if note_data.note_type is not None:
        note.note_type = note_data.note_type
    if note_data.content is not None:
        note.content = note_data.content
    if note_data.icon is not None:
        note.icon = note_data.icon

    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a note."""
    query = select(CalendarNote).where(
        CalendarNote.user_id == current_user.id,
        CalendarNote.date == note_date,
    )
    result = await db.execute(query)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found for this date",
        )

    await db.delete(note)
    await db.commit()
