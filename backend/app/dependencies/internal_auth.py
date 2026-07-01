import os
from fastapi import Header, HTTPException, status

# Read token from environment. Falls back to None (open) if not set,
# so existing demo deployments without the env var don't break.
_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN")


async def require_internal_token(
    x_internal_token: str = Header(default=None, alias="X-Internal-Token")
) -> None:
    """
    Light-weight guard for internal-only endpoints (e.g. driver registration).

    If INTERNAL_API_TOKEN is set in the environment, the request must supply
    a matching X-Internal-Token header. If the env var is not set (e.g. local
    demo run), the check is skipped so nothing breaks out of the box.
    """
    if _INTERNAL_TOKEN is None:
        # No token configured — open access (suitable for local / demo use)
        return

    if x_internal_token != _INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token header."
        )
