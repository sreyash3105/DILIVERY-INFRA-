import secrets

def generate_api_key() -> str:
    """Generates a secure random API key for a tenant."""
    return f"dep_{secrets.token_urlsafe(32)}"
