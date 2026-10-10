from django.urls import path

from trading import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/dashboard/", views.api_dashboard, name="api_dashboard"),
    path("api/agents/<int:agent_id>/start/", views.api_agent_start, name="api_agent_start"),
    path("api/agents/<int:agent_id>/stop/", views.api_agent_stop, name="api_agent_stop"),
    path("api/kill-switch/", views.api_kill_switch, name="api_kill_switch"),
    path("api/paper/reset/", views.api_paper_reset, name="api_paper_reset"),
    path("api/paper/add-funds/", views.api_paper_add_funds, name="api_paper_add_funds"),
    path("api/scan/", views.api_scan_now, name="api_scan_now"),
]
