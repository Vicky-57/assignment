from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models import AutoField


class UserSession(models.Model):
    #id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=100, unique=True,null=True, blank=True)
    preferences = models.JSONField(default=dict)
    room_type = models.CharField(max_length=50, null=True)
    style_preference = models.CharField(max_length=50, null=True)
    budget_range = models.CharField(max_length=50, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session {self.session_key[:8]}..."

class ChatInteraction(models.Model):
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    user_message = models.TextField()
    ai_response = models.TextField()
    intent = models.CharField(max_length=100, null=True)
    extracted_preferences = models.JSONField(default=dict)
    confidence_score = models.FloatField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']