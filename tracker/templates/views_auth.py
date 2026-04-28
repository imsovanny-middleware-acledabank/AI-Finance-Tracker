# tracker/views_auth.py
import json
import os
from datetime import timedelta

import httpx
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tracker.models import OTPSession, TelegramUser


def login_view(request):
    """Render login page with Telegram Login Widget."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    return render(request, "login.html", {"bot_token": bot_token})


@csrf_exempt
@require_http_methods(["POST"])
def telegram_login_callback(request):
    """Handle Telegram Login Widget callback."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    data = body.get("data", {})
    if not data:
        return JsonResponse({"error": "No data provided"}, status=400)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        return JsonResponse({"error": "Bot token not configured"}, status=500)

    # Verify the hash
    data_for_verify = data.copy()
    if not TelegramUser.verify_telegram_hash(data_for_verify, bot_token):
        return JsonResponse({"error": "Invalid hash"}, status=401)

    telegram_id = int(data.get("id", 0))
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    username = data.get("username", "")
    photo_url = data.get("photo_url", "")
    auth_date = int(data.get("auth_date", 0))

    # Create or update user
    user, created = TelegramUser.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "photo_url": photo_url,
            "auth_date": auth_date,
        },
    )

    # Set session
    request.session["telegram_id"] = telegram_id
    request.session["user_id"] = user.id
    request.session.set_expiry(86400 * 30)  # 30 days

    return JsonResponse(
        {
            "success": True,
            "telegram_id": telegram_id,
        }
    )


def user_view(request):
    """Get current authenticated user."""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    try:
        user = TelegramUser.objects.get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    # If first_name is missing, fetch from Telegram Bot API
    if not user.first_name:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if bot_token:
            try:
                resp = httpx.get(
                    f"https://api.telegram.org/bot{bot_token}/getChat",
                    params={"chat_id": telegram_id},
                    timeout=5,
                )
                if resp.status_code == 200:
                    chat_data = resp.json().get("result", {})
                    user.first_name = chat_data.get("first_name", "")
                    user.last_name = chat_data.get("last_name", "")
                    user.username = chat_data.get("username", "") or user.username
                    user.photo_url = user.photo_url  # keep existing
                    user.save(update_fields=["first_name", "last_name", "username"])
            except Exception:
                pass  # Fail silently, will show fallback

    return JsonResponse(
        {
            "id": user.telegram_id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
            "photo_url": user.photo_url or "",
        }
    )


@require_http_methods(["POST"])
def logout_view(request):
    """Logout user."""
    request.session.flush()
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def request_otp(request):
    """Request OTP for phone number login."""
    try:
        body = json.loads(request.body)
        phone_number = body.get("phone_number", "").strip()
        telegram_id = body.get("telegram_id")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not phone_number:
        return JsonResponse({"error": "Phone number required"}, status=400)

    if not telegram_id:
        return JsonResponse({"error": "Telegram ID required"}, status=400)

    # Validate and convert telegram_id to integer
    try:
        telegram_id_int = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid Telegram ID format"}, status=400)

    # Clean phone number (remove spaces, dashes, etc.)
    phone_clean = "".join(filter(str.isdigit, phone_number))
    if len(phone_clean) < 10:
        return JsonResponse({"error": "Invalid phone number"}, status=400)

    # Generate OTP
    otp_code = OTPSession.generate_otp()

    # Create OTP session (expires in 5 minutes)
    otp_session = OTPSession.objects.create(
        phone_number=phone_number,
        telegram_id=telegram_id_int,
        otp_code=otp_code,
        expires_at=timezone.now() + timedelta(minutes=5),
    )

    # Send OTP to user via Telegram bot
    try:
        send_otp_to_telegram(telegram_id_int, otp_code)
    except Exception as e:
        error_str = str(e)
        print(f"Error sending OTP: {error_str}")
        # Clean up orphaned session
        otp_session.delete()
        # Handle common Telegram errors
        if "chat not found" in error_str or "Forbidden" in error_str:
            return JsonResponse(
                {
                    "error": "Unable to send OTP. Please ensure you have started the bot on Telegram by sending /start to @AIFinancialTrackerBot."
                },
                status=400,
            )
        # Unexpected errors
        return JsonResponse(
            {"error": "Failed to send OTP. Please try again later."}, status=500
        )

    return JsonResponse(
        {
            "success": True,
            "message": "OTP sent to Telegram",
            "session_id": otp_session.id,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def verify_otp(request):
    """Verify OTP and create/update user."""
    try:
        body = json.loads(request.body)
        session_id = body.get("session_id")
        otp_code = body.get("otp_code", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not session_id or not otp_code:
        return JsonResponse({"error": "Session ID and OTP code required"}, status=400)

    try:
        otp_session = OTPSession.objects.get(id=session_id)
    except OTPSession.DoesNotExist:
        return JsonResponse({"error": "Invalid session"}, status=404)

    # Check if OTP is valid
    if otp_session.is_expired():
        return JsonResponse({"error": "OTP expired"}, status=400)

    if otp_session.attempt_count >= 5:
        return JsonResponse({"error": "Too many attempts"}, status=400)

    otp_session.attempt_count += 1
    otp_session.save()

    if otp_session.otp_code != otp_code:
        return JsonResponse({"error": "Invalid OTP"}, status=401)

    # OTP verified - create or update user
    otp_session.is_verified = True
    otp_session.save()

    # Create or update TelegramUser
    user, created = TelegramUser.objects.update_or_create(
        telegram_id=otp_session.telegram_id,
        defaults={
            "phone_number": otp_session.phone_number,
        },
    )

    # Set session
    request.session["telegram_id"] = otp_session.telegram_id
    request.session["user_id"] = user.id
    request.session.set_expiry(86400 * 30)  # 30 days

    return JsonResponse(
        {"success": True, "telegram_id": otp_session.telegram_id, "user_id": user.id}
    )


def send_otp_to_telegram(telegram_id, otp_code):
    """Send OTP to user via Telegram bot message."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise Exception("Bot token not configured")

    message = (
        f"🔐 Your OTP code is: <b>{otp_code}</b>\n\nDo not share this code with anyone."
    )

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = httpx.post(
            url,
            json={"chat_id": int(telegram_id), "text": message, "parse_mode": "HTML"},
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Telegram API error: {response.text}")

        return True
    except Exception as e:
        print(f"Failed to send OTP via Telegram: {e}")
        raise
