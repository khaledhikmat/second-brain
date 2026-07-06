"""API key authentication middleware for HTTP API."""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import logging

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str, configured_key: str) -> bool:
    """
    Verify the provided API key matches the configured key.

    Args:
        api_key: API key from request header
        configured_key: Configured API key from environment

    Returns:
        True if keys match, False otherwise
    """
    if not api_key or not configured_key:
        return False

    return api_key == configured_key


def create_api_key_dependency(configured_key: str):
    """
    Create an API key dependency function for FastAPI.

    Args:
        configured_key: The configured API key from environment

    Returns:
        Dependency function for FastAPI endpoints
    """
    async def api_key_dependency(api_key: str = Security(api_key_header)):
        """Verify API key from request header."""
        if not api_key:
            logger.warning("API request without API key")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key. Provide X-API-Key header."
            )

        if not verify_api_key(api_key, configured_key):
            logger.warning(f"API request with invalid API key: {api_key[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

        return api_key

    return api_key_dependency
