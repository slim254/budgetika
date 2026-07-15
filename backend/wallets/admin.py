from django.contrib import admin

from .models import (
    Transaction,
    Wallet,
    TransactionCategory,
    UserTransactionTag,
    RecurringTransaction,
    RecurringTransactionExecution,
    AIUsageLog,
    ModelPricing,
    UserAIQuota,
    ImportCategoryRule,
)

admin.site.register(Transaction)
admin.site.register(Wallet)
admin.site.register(TransactionCategory)
admin.site.register(UserTransactionTag)
admin.site.register(RecurringTransaction)
admin.site.register(RecurringTransactionExecution)


@admin.register(ImportCategoryRule)
class ImportCategoryRuleAdmin(admin.ModelAdmin):
    list_display = ("keyword", "category", "user", "updated_at")
    search_fields = ("keyword",)


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "model", "feature", "input_tokens", "output_tokens", "cost_usd", "created_at")
    list_filter = ("provider", "feature")
    search_fields = ("user__username", "user__email")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(ModelPricing)
class ModelPricingAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "input_cost", "output_cost", "valid_from")
    ordering = ("provider", "-valid_from")


@admin.register(UserAIQuota)
class UserAIQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "monthly_token_limit_display")

    def monthly_token_limit_display(self, obj):
        return obj.monthly_token_limit if obj.monthly_token_limit is not None else "default"
    monthly_token_limit_display.short_description = "Monthly Token Limit"
