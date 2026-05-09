"""Serve built SPA entrypoint through Django."""

from urllib.parse import quote

from django.shortcuts import redirect, render


def spa_index(request, path=None):
    """Serve the premium admin SPA index for all /app routes."""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        return redirect(f"/login/?next={quote(request.get_full_path() or '/app/')}")
    return render(request, "spa/index.html")
