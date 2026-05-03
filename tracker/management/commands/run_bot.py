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

        # --- Force clear Telegram polling via deleteWebhook API ---
        self.stdout.write("Clearing stale Telegram connections...")
        try:
            import urllib.request

            url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
            urllib.request.urlopen(url, timeout=10)
            self.stdout.write(self.style.SUCCESS("Telegram connection cleared."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"deleteWebhook warning: {e}"))

        time.sleep(2)

        self.stdout.write(self.style.SUCCESS("Bot is starting..."))

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

        async def _on_error(update, context):
            logger.error("Exception in handler:", exc_info=context.error)
            if update:
                logger.error("Update that caused error: %s", update)
            if isinstance(context.error, TelegramConflict):
                self.stdout.write(
                    self.style.ERROR(
                        "Telegram polling conflict: another bot instance is already running "
                        "(local or remote). Stop other instances and start only one."
                    )
                )
                await context.application.stop()

        def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = handle_uncaught_exception
        app.add_error_handler(_on_error)

        app.run_polling(
            drop_pending_updates=True, allowed_updates=["message", "callback_query"]
        )
