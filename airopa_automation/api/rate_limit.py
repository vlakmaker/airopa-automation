"""
Rate limiting configuration for the API

Uses slowapi to limit request rates and prevent abuse.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Get rate limit from environment or use defaults
# Format: "requests/period" e.g., "100/minute", "1000/hour"
DEFAULT_RATE_LIMIT = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
SCRAPE_RATE_LIMIT = os.getenv("RATE_LIMIT_SCRAPE", "5/minute")

# Create limiter instance using client IP as the key
limiter = Limiter(key_func=get_remote_address)
