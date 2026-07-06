"""
Dashboard handler for monitoring and analytics.

Provides a web-based dashboard with HTMX for real-time updates.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Form, Response, Cookie, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import secrets
import hashlib

from src.config import DASHBOARD_ENABLED, DASHBOARD_USERNAME, DASHBOARD_PASSWORD
from src.db.database import get_db_manager
from src.db.repository import MessageRepository, AnalyticsRepository

logger = logging.getLogger(__name__)

# Setup templates
BASE_DIR = Path(__file__).parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Simple session storage (in-memory, resets on restart)
# For production, use Redis or database
SESSIONS = set()

def create_session_token(username: str) -> str:
    """Create a secure session token."""
    token = secrets.token_urlsafe(32)
    SESSIONS.add(token)
    return token

def verify_session(token: Optional[str]) -> bool:
    """Verify if session token is valid."""
    return token in SESSIONS if token else False

def revoke_session(token: str):
    """Revoke a session token."""
    SESSIONS.discard(token)

async def get_current_user(session_token: Optional[str] = Cookie(None, alias="session")) -> str:
    """Dependency to get current user from session."""
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return DASHBOARD_USERNAME

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Dashboard home page - redirects to login or dashboard."""
    if not DASHBOARD_ENABLED:
        raise HTTPException(status_code=404, detail="Dashboard is disabled")

    if not verify_session(session_token):
        return RedirectResponse(url="/dashboard/login", status_code=302)

    return RedirectResponse(url="/dashboard/view", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Login page."""
    if not DASHBOARD_ENABLED:
        raise HTTPException(status_code=404, detail="Dashboard is disabled")

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Handle login form submission."""
    if not DASHBOARD_ENABLED:
        raise HTTPException(status_code=404, detail="Dashboard is disabled")

    # Verify credentials
    if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
        # Create session
        token = create_session_token(username)

        # Redirect to dashboard with session cookie
        response = RedirectResponse(url="/dashboard/view", status_code=302)
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax"
        )
        return response
    else:
        # Invalid credentials
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password"}
        )
        response.status_code = 401
        return response


@router.post("/logout")
async def logout(
    request: Request,
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Handle logout."""
    if session_token:
        revoke_session(session_token)

    response = RedirectResponse(url="/dashboard/login", status_code=302)
    response.delete_cookie("session")
    return response


@router.get("/view", response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    """Main dashboard view."""
    if not DASHBOARD_ENABLED:
        raise HTTPException(status_code=404, detail="Dashboard is disabled")

    db_manager = get_db_manager()

    if not db_manager or not db_manager.is_available:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "summary": {
                    "total_messages": 0,
                    "by_status": {},
                    "by_category": {},
                    "by_language": {},
                    "success_rate_percent": 0,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "categories": {},
                "queue": {
                    "queued_count": 0,
                    "queue": []
                }
            }
        )

    # Fetch analytics data
    async with db_manager.get_session() as session:
        # Summary
        total = await AnalyticsRepository.get_total_messages(session)
        by_status = await AnalyticsRepository.get_message_counts_by_status(session)
        by_category = await AnalyticsRepository.get_message_counts_by_category(session)
        by_language = await AnalyticsRepository.get_message_counts_by_language(session)
        success_rate = await AnalyticsRepository.get_success_rate(session)

        # Queue
        queued_messages = await MessageRepository.get_queued_messages(session, limit=10)

        # Categories with percentages
        categories = {}
        for cat, count in by_category.items():
            categories[cat] = {
                "count": count,
                "percentage": round((count / total * 100) if total > 0 else 0, 1)
            }

        # Queue data
        queue_data = {
            "queued_count": by_status.get("queued", 0),
            "queue": [
                {
                    "id": msg.id,
                    "timestamp": msg.timestamp,
                    "status": msg.processing_status.value,
                    "text_preview": msg.raw_text[:100] if msg.raw_text else ""
                }
                for msg in queued_messages
            ]
        }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "summary": {
                "total_messages": total,
                "by_status": by_status,
                "by_category": by_category,
                "by_language": by_language,
                "success_rate_percent": success_rate,
                "timestamp": datetime.utcnow().isoformat()
            },
            "categories": categories,
            "queue": queue_data
        }
    )


@router.get("/refresh", response_class=HTMLResponse)
async def dashboard_refresh(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    """
    Refresh endpoint for HTMX auto-updates.
    Returns only the refreshable content fragment (not the full page).
    """
    if not DASHBOARD_ENABLED:
        raise HTTPException(status_code=404, detail="Dashboard is disabled")

    db_manager = get_db_manager()

    if not db_manager or not db_manager.is_available:
        return templates.TemplateResponse(
            request=request,
            name="dashboard_content.html",
            context={
                "summary": {
                    "total_messages": 0,
                    "by_status": {},
                    "by_category": {},
                    "by_language": {},
                    "success_rate_percent": 0,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "categories": {},
                "queue": {
                    "queued_count": 0,
                    "queue": []
                }
            }
        )

    # Fetch analytics data
    async with db_manager.get_session() as session:
        # Summary
        total = await AnalyticsRepository.get_total_messages(session)
        by_status = await AnalyticsRepository.get_message_counts_by_status(session)
        by_category = await AnalyticsRepository.get_message_counts_by_category(session)
        by_language = await AnalyticsRepository.get_message_counts_by_language(session)
        success_rate = await AnalyticsRepository.get_success_rate(session)

        # Queue
        queued_messages = await MessageRepository.get_queued_messages(session, limit=10)

        # Categories with percentages
        categories = {}
        for cat, count in by_category.items():
            categories[cat] = {
                "count": count,
                "percentage": round((count / total * 100) if total > 0 else 0, 1)
            }

        # Queue data
        queue_data = {
            "queued_count": by_status.get("queued", 0),
            "queue": [
                {
                    "id": msg.id,
                    "timestamp": msg.timestamp,
                    "status": msg.processing_status.value,
                    "text_preview": msg.raw_text[:100] if msg.raw_text else ""
                }
                for msg in queued_messages
            ]
        }

    return templates.TemplateResponse(
        request=request,
        name="dashboard_content.html",
        context={
            "summary": {
                "total_messages": total,
                "by_status": by_status,
                "by_category": by_category,
                "by_language": by_language,
                "success_rate_percent": success_rate,
                "timestamp": datetime.utcnow().isoformat()
            },
            "categories": categories,
            "queue": queue_data
        }
    )
