"""Webhook endpoints for external service integrations.

This module handles webhooks from:
- Clerk (user authentication events)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk_auth import verify_webhook_signature
from app.core.config import get_settings
from app.core.database import get_db
from app.core.debug_utils import CloudMigrationDebug
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ======================
# Clerk Webhooks
# ======================

@router.post("/clerk")
async def handle_clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    svix_id: str = Header(..., alias="svix-id"),
    svix_timestamp: str = Header(..., alias="svix-timestamp"),
    svix_signature: str = Header(..., alias="svix-signature"),
) -> Dict[str, Any]:
    """Handle Clerk webhook events.

    Clerk sends webhooks for user lifecycle events:
    - user.created: New user registered
    - user.updated: User profile updated
    - user.deleted: User account deleted

    Args:
        request: FastAPI request object
        db: Database session
        svix_id: Svix webhook ID header
        svix_timestamp: Svix timestamp header
        svix_signature: Svix signature header

    Returns:
        Acknowledgment response

    Raises:
        HTTPException: If signature verification fails
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    if not verify_webhook_signature(body, svix_id, svix_timestamp, svix_signature):
        logger.warning(f"Clerk webhook signature verification failed: svix_id={svix_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Parse webhook payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Clerk webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    event_type = payload.get("type")
    event_data = payload.get("data", {})
    clerk_user_id = event_data.get("id")

    logger.info(f"Received Clerk webhook: type={event_type}, clerk_user_id={clerk_user_id}")

    # Route to appropriate handler
    try:
        if event_type == "user.created":
            await _handle_user_created(db, event_data)
            CloudMigrationDebug.log_webhook_event(
                event_type=event_type,
                clerk_user_id=clerk_user_id,
                success=True,
            )
        elif event_type == "user.updated":
            await _handle_user_updated(db, event_data)
            CloudMigrationDebug.log_webhook_event(
                event_type=event_type,
                clerk_user_id=clerk_user_id,
                success=True,
            )
        elif event_type == "user.deleted":
            await _handle_user_deleted(db, clerk_user_id)
            CloudMigrationDebug.log_webhook_event(
                event_type=event_type,
                clerk_user_id=clerk_user_id,
                success=True,
            )
        else:
            logger.debug(f"Ignoring unhandled Clerk event type: {event_type}")

        return {"status": "ok", "event_type": event_type}

    except Exception as e:
        logger.error(f"Error processing Clerk webhook {event_type}: {e}")
        CloudMigrationDebug.log_webhook_event(
            event_type=event_type,
            clerk_user_id=clerk_user_id,
            success=False,
            error=str(e),
        )
        # Return success to prevent Clerk from retrying
        # Log the error for manual investigation
        return {"status": "error", "event_type": event_type, "error": str(e)}


async def _handle_user_created(db: AsyncSession, event_data: Dict[str, Any]) -> None:
    """Handle user.created webhook event.

    Creates a new user in the database if they don't exist,
    or links Clerk ID to existing account with same email.

    Args:
        db: Database session
        event_data: Clerk user data
    """
    clerk_user_id = event_data.get("id")
    if not clerk_user_id:
        logger.error("user.created event missing user ID")
        return

    # Check if user already exists by Clerk ID
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.debug(f"User already exists for Clerk ID: {clerk_user_id}")
        return

    # Extract email
    email_addresses = event_data.get("email_addresses", [])
    primary_email = None
    primary_email_id = event_data.get("primary_email_address_id")

    for email_obj in email_addresses:
        if email_obj.get("id") == primary_email_id:
            primary_email = email_obj.get("email_address")
            break

    if not primary_email and email_addresses:
        primary_email = email_addresses[0].get("email_address")

    if not primary_email:
        logger.error(f"user.created event missing email for Clerk ID: {clerk_user_id}")
        return

    # Check if user with same email already exists (account linking)
    stmt = select(User).where(User.email == primary_email)
    result = await db.execute(stmt)
    email_user = result.scalar_one_or_none()

    if email_user:
        # Link Clerk ID to existing account
        email_user.clerk_user_id = clerk_user_id
        await db.commit()
        logger.info(f"Linked Clerk ID to existing user from webhook: id={email_user.id}, email={primary_email}")
        return

    # Create display name
    first_name = event_data.get("first_name", "") or ""
    last_name = event_data.get("last_name", "") or ""
    display_name = f"{first_name} {last_name}".strip() or primary_email.split("@")[0]

    # Create new user
    user = User(
        clerk_user_id=clerk_user_id,
        email=primary_email,
        display_name=display_name,
        password_hash=None,
    )
    db.add(user)
    await db.commit()

    logger.info(f"Created user from webhook: id={user.id}, email={primary_email}, clerk_id={clerk_user_id}")


async def _handle_user_updated(db: AsyncSession, event_data: Dict[str, Any]) -> None:
    """Handle user.updated webhook event.

    Updates user profile information in the database.

    Args:
        db: Database session
        event_data: Clerk user data
    """
    clerk_user_id = event_data.get("id")
    if not clerk_user_id:
        logger.error("user.updated event missing user ID")
        return

    # Find user
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"user.updated event for unknown Clerk ID: {clerk_user_id}")
        # Create user if they don't exist (edge case)
        await _handle_user_created(db, event_data)
        return

    # Update email if changed
    email_addresses = event_data.get("email_addresses", [])
    primary_email_id = event_data.get("primary_email_address_id")
    new_email = None

    for email_obj in email_addresses:
        if email_obj.get("id") == primary_email_id:
            new_email = email_obj.get("email_address")
            break

    if new_email and new_email != user.email:
        logger.info(f"Updating email for user {user.id}: {user.email} -> {new_email}")
        user.email = new_email

    # Update display name if changed
    first_name = event_data.get("first_name", "") or ""
    last_name = event_data.get("last_name", "") or ""
    new_display_name = f"{first_name} {last_name}".strip()

    if new_display_name and new_display_name != user.display_name:
        logger.info(f"Updating display_name for user {user.id}: {user.display_name} -> {new_display_name}")
        user.display_name = new_display_name

    await db.commit()
    logger.debug(f"Updated user from webhook: id={user.id}, clerk_id={clerk_user_id}")


async def _handle_user_deleted(db: AsyncSession, clerk_user_id: str) -> None:
    """Handle user.deleted webhook event.

    Soft-deletes or marks user as inactive. Does NOT delete user data
    to preserve activity history and prevent data loss.

    Args:
        db: Database session
        clerk_user_id: Clerk user ID
    """
    if not clerk_user_id:
        logger.error("user.deleted event missing user ID")
        return

    # Find user
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"user.deleted event for unknown Clerk ID: {clerk_user_id}")
        return

    # Soft delete: Clear clerk_user_id to prevent login, but preserve data
    # This allows re-linking if the same email registers again
    logger.info(f"Soft-deleting user from webhook: id={user.id}, clerk_id={clerk_user_id}")

    user.clerk_user_id = None  # Prevent Clerk login
    # Optionally add a deleted_at timestamp if you add that column

    await db.commit()
    logger.info(f"User soft-deleted: id={user.id}")


# ======================
# Health Check Endpoint
# ======================

@router.get("/health")
async def webhook_health() -> Dict[str, Any]:
    """Health check for webhook endpoint.

    Returns:
        Health status and configuration info
    """
    return {
        "status": "ok",
        "clerk_webhooks_enabled": bool(settings.clerk_webhook_secret),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
