"""Telegram bot management command — thin entry point."""
import logging
import os
import sys

from django.core.management.base import BaseCommand
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .callback_handler import handle_quick_action
from .command_handlers import BotCommandHandlers
from .message_processor import handle_message

logger = logging.getLogger(__name__)


def _build_application():
    """Create and configure telegram application with all handlers."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    # Register all /command handlers
    BotCommandHandlers.register_all(app)

    # Inline keyboard callback handler
    app.add_handler(CallbackQueryHandler(handle_quick_action))

    # Message handler for text, voice, photo, and documents
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.VOICE | filters.PHOTO | filters.Document.ALL)
            & (~filters.COMMAND),
            handle_message,
        )
    )

    return app


class Command(BaseCommand):
    help = "Runs the Telegram bot"

    def handle(self, *args, **options):
        import atexit
        import fcntl
        import time

        from telegram.error import Conflict as TelegramConflict

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in .env"))
            return

        # --- Prevent multiple local run_bot instances ---
        lock_path = "/tmp/ai_finance_bot_run_bot.lock"
        lock_file = open(lock_path, "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except BlockingIOError:
            self.stdout.write(
                self.style.ERROR(
                    "Another local run_bot instance is already running. "
                    "Stop it first (e.g., pkill -f 'manage.py run_bot') and retry."
                )
            )
            return

        def _release_lock():
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass

        atexit.register(_release_lock)

        mode = os.getenv("BOT_MODE", "polling").strip().lower()
        if mode not in {"polling", "webhook"}:
            self.stdout.write(
                self.style.WARNING(
                    f"Unknown BOT_MODE='{mode}', fallback to 'polling'."
                )
            )
            mode = "polling"

        if mode == "polling":
            # --- Force clear webhook state before polling ---
            self.stdout.write("Clearing stale Telegram webhook before polling...")
            try:
                import urllib.request

                url = (
                    f"https://api.telegram.org/bot{token}"
                    "/deleteWebhook?drop_pending_updates=true"
                )
                urllib.request.urlopen(url, timeout=10)
                self.stdout.write(self.style.SUCCESS("Telegram webhook cleared."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"deleteWebhook warning: {e}"))

            time.sleep(2)

        self.stdout.write(self.style.SUCCESS(f"Bot is starting in {mode} mode..."))

        app = _build_application()

        async def _on_error(update, context):
            if isinstance(context.error, TelegramConflict):
                logger.warning(
                    "Telegram polling conflict detected (another getUpdates instance is active)."
                )
                self.stdout.write(
                    self.style.ERROR(
                        "Telegram polling conflict: another bot instance is already running "
                        "(local or remote). Stop other instances and start only one."
                    )
                )
                return

            logger.error("Exception in handler:", exc_info=context.error)
            if update:
                logger.error("Update that caused error: %s", update)

        def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = handle_uncaught_exception
        app.add_error_handler(_on_error)

        if mode == "webhook":
            webhook_path = os.getenv("BOT_WEBHOOK_PATH", "telegram/webhook").strip()
            webhook_path = webhook_path.strip("/")

            webhook_base_url = os.getenv("BOT_WEBHOOK_BASE_URL", "").strip()
            explicit_webhook_url = os.getenv("BOT_WEBHOOK_URL", "").strip()
            if explicit_webhook_url:
                webhook_url = explicit_webhook_url
            else:
                if not webhook_base_url:
                    self.stdout.write(
                        self.style.ERROR(
                            "Webhook mode requires BOT_WEBHOOK_URL or BOT_WEBHOOK_BASE_URL"
                        )
                    )
                    return
                webhook_url = f"{webhook_base_url.rstrip('/')}/{webhook_path}"

            port = int(os.getenv("PORT", "10000"))
            self.stdout.write(self.style.SUCCESS(f"Webhook URL: {webhook_url}"))
            self.stdout.write(self.style.SUCCESS(f"Listening on 0.0.0.0:{port}"))

            app.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=webhook_path,
                webhook_url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
            )
        else:
            retry_seconds = int(os.getenv("BOT_CONFLICT_RETRY_SECONDS", "15"))
            while True:
                try:
                    app.run_polling(
                        drop_pending_updates=True,
                        allowed_updates=["message", "callback_query"],
                    )
                    break
                except TelegramConflict:
                    self.stdout.write(
                        self.style.WARNING(
                            "Telegram polling conflict detected. "
                            f"Retrying in {retry_seconds}s (ensure only one active bot instance)."
                        )
                    )
                    time.sleep(retry_seconds)
                    # Recreate app for a clean retry cycle
                    app = _build_application()
