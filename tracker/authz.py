"""Role-based access helpers for session-authenticated Telegram users."""

import os

READ_ROLES = {"viewer", "manager", "admin"}
# In this mini-app, regular signed-in users (viewer) should be able to add/update/delete
# their own transactions. Manager/admin remain elevated for broader operations.
WRITE_ROLES = {"viewer", "manager", "admin"}
ADMIN_ROLES = {"admin"}


def _parse_role_ids(env_name: str) -> set[int]:
    raw = os.getenv(env_name, "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return ids


def role_for_telegram_id(telegram_id: int | None) -> str:
    """Resolve role from configured Telegram ID allowlists."""
    if telegram_id is None:
        return "viewer"

    admin_ids = _parse_role_ids("ADMIN_TELEGRAM_IDS")
    manager_ids = _parse_role_ids("MANAGER_TELEGRAM_IDS")

    if telegram_id in admin_ids:
        return "admin"
    if telegram_id in manager_ids:
        return "manager"
    return "viewer"


def can_write(role: str) -> bool:
    return role in WRITE_ROLES


def is_admin(role: str) -> bool:
    return role in ADMIN_ROLES
