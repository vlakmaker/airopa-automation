"""
API Authentication module

Provides API key authentication for protected endpoints.
"""

import logging
import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# API key header configuration
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key() -> Optional[str]:
    """Get the API key from environment variable."""
    return os.getenv("API_KEY")


async def verify_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """
    Verify the API key from the request header.

    This dependency can be used to protect endpoints that require authentication.

    Usage:
        @router.post("/protected")
        async def protected_endpoint(api_key: str = Depends(verify_api_key)):
            # Only accessible with valid API key
            pass

    Raises:
        HTTPException: 401 if API key is missing
        HTTPException: 403 if API key is invalid
    """
    expected_key = get_api_key()

    # If no API key is configured, allow access (for development)
    # In production, always set the API_KEY environment variable
    if not expected_key:
        logger.warning(
            "API_KEY environment variable not set. "
            "Endpoint is unprotected. Set API_KEY in production!"
        )
        return "no_key_configured"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != expected_key:
        logger.warning("Invalid API key attempted")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key
