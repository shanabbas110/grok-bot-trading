from django.contrib import admin

from trading.models import (
    ActivityLog,
    Agent,
    AppSettings,
    BalanceSnapshot,
    Execution,
    Order,
    Position,
    ScannedToken,
    TokenStatus,
    Trade,
)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "color", "last_tick_at")


admin.site.register(AppSettings)
admin.site.register(ScannedToken)
admin.site.register(TokenStatus)
admin.site.register(Order)
admin.site.register(Execution)
admin.site.register(Position)
admin.site.register(Trade)
admin.site.register(BalanceSnapshot)
admin.site.register(ActivityLog)
