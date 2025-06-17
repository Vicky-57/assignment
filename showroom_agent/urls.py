from django.urls import path
from . import views

urlpatterns = [
    path('start-session/', views.StartSessionView.as_view(), name='start_session'),
    path('chat/', views.ChatView.as_view(), name='chat'),
    path('session/<int:session_id>/', views.SessionStatusView.as_view(), name='session_status'),
]