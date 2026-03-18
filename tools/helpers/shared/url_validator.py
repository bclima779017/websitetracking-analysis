"""
URL validation module — Stage 1 of the diagnostic pipeline.

Validates URL accessibility, DNS resolution, and follows redirect chains.
Uses httpx for async HTTP requests.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx

from .config import UrlValidationResult


async def validate_url(url: str) -> UrlValidationResult:
    """
    Validate URL accessibility, DNS resolution, and redirect chain.

    Checks:
    1. DNS resolution of domain
    2. HTTP(S) connectivity
    3. Follows all redirects to final URL
    4. Returns final status code and redirect chain

    Args:
        url: Full URL to validate (e.g., https://example.com)

    Returns:
        UrlValidationResult with accessibility status and redirect chain

    Raises:
        httpx.RequestError: If network error occurs (non-fatal, caught internally)
        ValueError: If URL format is invalid
    """
    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL format: {url}")

    redirect_chain: list[str] = []
    final_url = url
    status_code = 0
    is_accessible = False
    error_msg: str | None = None
    dns_resolves = False
    is_https = False

    try:
        # Check DNS resolution
        try:
            await asyncio.get_event_loop().getaddrinfo(parsed.netloc, 443)
            dns_resolves = True
        except OSError:
            try:
                await asyncio.get_event_loop().getaddrinfo(parsed.netloc, 80)
                dns_resolves = True
            except OSError as e:
                dns_resolves = False
                error_msg = f"DNS resolution failed: {e}"

        # Make request with redirect following
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(10.0),
            verify=False,  # Allow self-signed certs
        ) as client:
            response = await client.get(url)

            status_code = response.status_code
            is_accessible = 200 <= status_code < 400
            final_url = str(response.url)

            is_https = final_url.startswith("https://")

            # Extract redirect chain from history
            if response.history:
                redirect_chain = [str(r.url) for r in response.history]

    except httpx.TimeoutException:
        error_msg = "Request timeout (10s)"
        status_code = 0
    except httpx.ConnectError as e:
        error_msg = f"Connection failed: {e}"
        status_code = 0
    except httpx.RequestError as e:
        error_msg = f"Request error: {e}"
        status_code = 0
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        status_code = 0

    return UrlValidationResult(
        url=url,
        final_url=final_url,
        is_accessible=is_accessible,
        status_code=status_code,
        redirect_chain=redirect_chain,
        is_https=is_https,
        dns_resolves=dns_resolves,
        error=error_msg,
    )
