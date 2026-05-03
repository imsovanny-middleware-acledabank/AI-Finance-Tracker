from django.contrib import admin

from .models import Budget, Category, ChatMessage, OTPSession, TelegramUser, Transaction

admin.site.site_header = "AI Finance Bot Administration"
admin.site.site_title = "AI Finance Bot Admin"
admin.site.index_title = "Control Center"


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
	list_display = (
		"telegram_id",
		"first_name",
		"last_name",
		"username",
		"phone_number",
		"created_at",
	)
	search_fields = (
		"=telegram_id",
		"first_name",
		"last_name",
		"username",
		"phone_number",
	)
	list_filter = ("created_at",)
	ordering = ("-created_at",)
	list_per_page = 25


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ("id", "icon", "name", "description", "created_at")
	search_fields = ("name", "description")
	ordering = ("name",)
	list_per_page = 25


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"telegram_id",
		"transaction_date",
		"transaction_type",
		"amount",
		"currency",
		"category_name",
		"created_at",
	)
	search_fields = ("=telegram_id", "category_name", "note", "tags")
	list_filter = ("transaction_type", "currency", "transaction_date", "created_at")
	ordering = ("-transaction_date", "-created_at")
	date_hierarchy = "transaction_date"
	list_select_related = ("category",)
	autocomplete_fields = ("category",)
	list_per_page = 30
	readonly_fields = ("created_at", "amount_usd", "amount_khr")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"telegram_id",
		"category",
		"limit_amount",
		"frequency",
		"alert_threshold",
		"is_active",
		"created_at",
	)
	search_fields = ("=telegram_id", "category__name")
	list_filter = ("frequency", "is_active", "created_at")
	ordering = ("-created_at",)
	autocomplete_fields = ("category",)
	list_per_page = 25
	readonly_fields = ("created_at", "updated_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"telegram_id",
		"conversation_id",
		"role",
		"short_message",
		"created_at",
	)
	search_fields = ("=telegram_id", "conversation_id", "message")
	list_filter = ("role", "created_at")
	ordering = ("-created_at",)
	list_per_page = 40
	readonly_fields = (
		"telegram_id",
		"conversation_id",
		"role",
		"message",
		"created_at",
	)

	@admin.display(description="Message")
	def short_message(self, obj: ChatMessage):
		msg = (obj.message or "").strip()
		return msg[:80] + ("…" if len(msg) > 80 else "")


@admin.register(OTPSession)
class OTPSessionAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"phone_number",
		"telegram_id",
		"otp_code",
		"is_verified",
		"attempt_count",
		"created_at",
		"expires_at",
	)
	search_fields = ("phone_number", "telegram_id", "otp_code")
	list_filter = ("is_verified", "created_at", "expires_at")
	ordering = ("-created_at",)
	list_per_page = 40
