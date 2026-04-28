# tracker/auth.py
"""
Telegram authentication module for the AI Finance Bot.
Provides secure login using Telegram user verification.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from django.core.cache import cache
from django.http import JsonResponse
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")


class TelegramAuthenticator:
    """Handles Telegram user authentication and verification."""

    @staticmethod
    def verify_telegram_data(telegram_data: Dict) -> Optional[Dict]:
        """
        Verify that telegram data is authentic and from Telegram.
        Returns verified user data or None if verification fails.

        Args:
            telegram_data: Dictionary with 'id', 'first_name', 'username', 'auth_date', 'hash'

        Returns:
            Verified user data or None
        """
        try:
            # Extract hash from data
            received_hash = telegram_data.get("hash")
            if not received_hash:
                return None

            # Create data check string (must be alphabetically sorted)
            data_check_string = "\n".join(
                f"{k}={v}" for k, v in sorted(telegram_data.items()) if k != "hash"
            )

            # Calculate expected hash
            secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
            expected_hash = hmac.new(
                secret_key, data_check_string.encode(), hashlib.sha256
            ).hexdigest()

            # Verify hash matches
            if received_hash != expected_hash:
                print("❌ Hash verification failed")
                return None

            # Verify auth_date is recent (within 24 hours)
            auth_date = int(telegram_data.get("auth_date", 0))
            current_time = int(datetime.now().timestamp())

            if current_time - auth_date > 86400:  # 24 hours
                print("❌ Auth data expired")
                return None

            # Verification successful
            return {
                "id": int(telegram_data.get("id")),
                "first_name": telegram_data.get("first_name", ""),
                "last_name": telegram_data.get("last_name", ""),
                "username": telegram_data.get("username", ""),
                "auth_date": auth_date,
                "photo_url": telegram_data.get("photo_url", ""),
            }

        except Exception as e:
            print(f"Error verifying Telegram data: {e}")
            return None

    @staticmethod
    def create_session(user_data: Dict) -> str:
        """
        Create a secure session for authenticated user.

        Args:
            user_data: Verified Telegram user data

        Returns:
            Session token
        """
        session_token = hashlib.sha256(
            f"{user_data['id']}{datetime.now().timestamp()}".encode()
        ).hexdigest()

        # Store session in cache (expires in 7 days)
        cache.set(f"telegram_session:{session_token}", user_data, timeout=7 * 24 * 3600)  # 7 days

        return session_token

    @staticmethod
    def get_session_user(session_token: str) -> Optional[Dict]:
        """
        Get user data from session token.

        Args:
            session_token: Session token

        Returns:
            User data or None if session invalid/expired
        """
        return cache.get(f"telegram_session:{session_token}")

    @staticmethod
    def logout_session(session_token: str) -> None:
        """Invalidate a session."""
        cache.delete(f"telegram_session:{session_token}")


def telegram_login_required(view_func):
    """
    Decorator to require Telegram authentication.
    """

    def wrapper(request, *args, **kwargs):
        session_token = request.COOKIES.get("telegram_session")

        if not session_token:
            return JsonResponse(
                {"error": "Not authenticated. Please login with Telegram."}, status=401
            )

        user_data = TelegramAuthenticator.get_session_user(session_token)
        if not user_data:
            return JsonResponse({"error": "Session expired. Please login again."}, status=401)

        # Attach user data to request
        request.telegram_user = user_data
        request.session_token = session_token

        return view_func(request, *args, **kwargs)

    return wrapper
