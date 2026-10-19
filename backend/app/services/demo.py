"""Sign-in details for public demonstration instances (off unless DEMO_PUBLIC_ACCOUNTS is set).

The seed gives these accounts DEMO_PUBLIC_PASSWORD; every other account, Admin included, keeps a random
password. The password comes from configuration, so nothing new is stored in plain text.
"""

from app.core.config import Settings

# (role, username or card number). Admin is deliberately absent: visitors must not administer the demo.
PUBLIC_ACCOUNTS = [
    ("Librarian", "librarian"),
    ("CirculationClerk", "clerk"),
    ("Auditor", "auditor"),
    ("Patron", "B00001"),
]


def public_accounts(settings: Settings) -> list[dict[str, str]]:
    if not settings.demo_public_accounts:
        return []
    return [
        {"role": role, "username": username, "password": settings.demo_public_password}
        for role, username in PUBLIC_ACCOUNTS
    ]


def public_password_for(settings: Settings, username: str) -> str | None:
    """The demo password for a public account, or None (the seed then generates a random one)."""
    if settings.demo_public_password and username in {u for _, u in PUBLIC_ACCOUNTS}:
        return settings.demo_public_password
    return None
