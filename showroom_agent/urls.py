from django.urls import path
from . import views

urlpatterns = [
    path('start-session/', views.StartSessionView.as_view(), name='start_session'),
    path('chat/', views.ChatView.as_view(), name='chat'),
    path('session/<int:session_id>/', views.SessionStatusView.as_view(), name='session_status'),
    path('api/quick-recommendations/', views.QuickRecommendationView.as_view(), name='quick_recommendations'),
    path('api/admin/cleanup/', views.SessionCleanupView.as_view(), name='session_cleanup'),

]