"""
HTTP handler implementation using FastAPI.
"""
import datetime
import secrets
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Depends, status, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature

from src.services.setting.typex import ISettingService
from src.services.logger.typex import ILoggerService
from src.services.data.typex import IDataService
from src.channels.telegram.typex import ITelegramHandler
from src.channels.http.typex import NoteRequest, NoteResponse

class HttpHandler:
    """
    HTTP handler implementation using FastAPI.
    Implements the IHttpHandler protocol.
    """

    def __init__(
        self,
        setting: ISettingService, 
        logger: ILoggerService,
        db_service: IDataService,
        telegram_handler: ITelegramHandler,
        lifespan=None
    ):
        """
        Initialize the HTTP handler.

        Args:
            db_service: Database service instance
            telegram_handler: Telegram handler instance
            lifespan: Optional lifespan context manager for FastAPI
        """
        self._setting = setting
        self._logger = logger        
        self._db_service = db_service
        self._telegram_handler = telegram_handler
        self.api_key = self._setting.get_api_key()
        self.admin_username = self._setting.get_admin_username()
        self.admin_password = self._setting.get_admin_password()
        self.templates_dir = self._setting.get_templates_dir()

        # Session management
        self.secret_key = secrets.token_urlsafe(32)
        self.serializer = URLSafeTimedSerializer(self.secret_key)

        # Create FastAPI app with optional lifespan
        self.app = FastAPI(
            title="Second Brain API",
            description="API for managing Second Brain operations, including Telegram webhooks and team management.",
            version="1.0.0",
            lifespan=lifespan
        )

        # Set up templates
        self.templates = Jinja2Templates(directory=self.templates_dir)

        # Register routes
        self._register_routes()

    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app

    async def initialize(self) -> None:
        """Initialize the HTTP handler."""
        self._logger.info("HTTP handler initialized")

    async def shutdown(self) -> None:
        """Cleanup when shutting down."""
        self._logger.info("HTTP handler shutdown")

    # ========================================================================
    # Authentication Helpers
    # ========================================================================

    def _create_session_token(self, username: str) -> str:
        """Create a signed session token."""
        return self.serializer.dumps(username, salt="session")

    def _verify_session_token(self, token: str) -> Optional[str]:
        """Verify session token and return username if valid."""
        try:
            # Token expires after 24 hours
            username = self.serializer.loads(token, salt="session", max_age=86400)
            return username
        except (BadSignature, Exception):
            return None

    def _get_current_user(self, request: Request) -> str:
        """Get current logged-in user from session cookie."""
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"}
            )

        username = self._verify_session_token(session_token)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"}
            )

        return username

    def _verify_api_key(self, request: Request) -> bool:
        """Verify API key from request headers."""
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != self.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key"
            )
        return True

    # ========================================================================
    # Route Registration
    # ========================================================================

    def _register_routes(self) -> None:
        """Register all routes."""

        # Health check endpoint
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy"}

        # Telegram webhook endpoint
        @self.app.post("/webhook/telegram")
        async def telegram_webhook(request: Request):
            """Handle Telegram webhook updates."""
            try:
                update_data = await request.json()
                await self._telegram_handler.handle_webhook(update_data)
                return {"ok": True}
            except Exception as e:
                self._logger.error(f"Error processing Telegram webhook: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process webhook"
                )

        # Note endpoints (API key required)
        @self.app.post(
            "/api/v1/notes",
            response_model=NoteResponse,
            responses={
                401: {"model": NoteResponse},
                500: {"model": NoteResponse}
            },
            tags=["Notes"]
        )
        async def create_note(
            request: NoteRequest,
            api_key: str = Depends(self._verify_api_key)
        ):
            """
            Create a note from text message.

            Processes the message with Claude AI and creates a structured Obsidian note.
            """
            try:
                self._logger.info(f"Received note creation request (length: {len(request.message)} chars)")

                # Build message text with category prefix if provided
                message_text = request.message
                category = request.category if request.category else "jot"

                # Enqueue the message
                created_message = await self._db_service.create_message(
                    raw_text=message_text,
                    category=category,
                    channel="http"
                )

                return NoteResponse(
                    success=True,
                    message="Message queued for batch processing",
                    message_id=created_message.id,
                    status="queued"
                )

            except Exception as e:
                self._logger.error(f"Error creating note: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create note: {str(e)}"
                )

        # Dashboard endpoint (API key required)
        # Login page
        @self.app.get("/login", response_class=HTMLResponse)
        async def login_page(request: Request):
            """Serve the login page."""
            return self.templates.TemplateResponse(
                "login.html",
                {"request": request, "error": None}
            )

        # Login form handler
        @self.app.post("/login")
        async def login(
            request: Request,
            username: str = Form(...),
            password: str = Form(...)
        ):
            """Handle login form submission."""
            # Verify credentials
            if username == self.admin_username and password == self.admin_password:
                # Create session token
                token = self._create_session_token(username)

                # Redirect to dashboard with session cookie
                response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
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
                return self.templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "error": "Invalid username or password"
                    },
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

        # Logout
        @self.app.get("/logout")
        async def logout():
            """Logout and clear session."""
            response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
            response.delete_cookie("session")
            return response

        # Stats cards endpoint for HTMX refresh
        @self.app.get("/api/stats-cards", response_class=HTMLResponse)
        async def stats_cards(
            request: Request,
            _: str = Depends(self._get_current_user)
        ):
            """Return just the stats cards HTML for HTMX refresh."""
            try:
                stats = await self.db_service.get_stats()

                stats_html = f"""
            <div class="stat-card teams">
                <h3>Total Teams</h3>
                <div class="value">{stats.total_teams}</div>
            </div>

            <div class="stat-card recipients">
                <h3>Total Recipients</h3>
                <div class="value">{stats.total_recipients}</div>
            </div>

            <div class="stat-card evaluators">
                <h3>Total Evaluators</h3>
                <div class="value">{stats.total_evaluators}</div>
            </div>

            <div class="stat-card total">
                <h3>Total Evaluations</h3>
                <div class="value">{stats.total_evaluations}</div>
            </div>

            <div class="stat-card queued">
                <h3>Queued</h3>
                <div class="value">{stats.queued_evaluations}</div>
            </div>

            <div class="stat-card processing">
                <h3>Processing</h3>
                <div class="value">{stats.processing_evaluations}</div>
            </div>

            <div class="stat-card completed">
                <h3>Completed</h3>
                <div class="value">{stats.completed_evaluations}</div>
            </div>

            <div class="stat-card failed">
                <h3>Failed</h3>
                <div class="value">{stats.failed_evaluations}</div>
            </div>
                """
                return HTMLResponse(content=stats_html)

            except Exception as e:
                self._logger.error(f"Error loading stats: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to load statistics"
                )

        # Admin dashboard (requires session auth)
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(
            request: Request,
            _: str = Depends(self._get_current_user)
        ):
            """Serve the admin dashboard."""
            try:
                # Summary
                total = await self._db_service.get_total_messages()
                by_status = await self._db_service.get_message_counts_by_status()
                by_category = await self._db_service.get_message_counts_by_category()
                by_language = await self._db_service.get_message_counts_by_language()
                success_rate = await self._db_service.get_success_rate()

                # Queue
                queued_messages = await self._db_service.get_queued_messages(limit=10)

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

                return self.templates.TemplateResponse(
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
            except Exception as e:
                self._logger.error(f"Error loading dashboard: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to load dashboard"
                )
