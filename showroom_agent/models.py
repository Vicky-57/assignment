from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class UserSession(models.Model):
    """Simplified user session model"""
    
    ROOM_TYPE_CHOICES = [
        ('bathroom', 'Bathroom'),
        ('kitchen', 'Kitchen'),
        ('other', 'Other'),
    ]
    
    STYLE_CHOICES = [
        ('modern', 'Modern'),
        ('traditional', 'Traditional'),
        ('contemporary', 'Contemporary'),
        ('rustic', 'Rustic'),
        ('minimalist', 'Minimalist'),
        ('industrial', 'Industrial'),
    ]
    
    BUDGET_CHOICES = [
        ('low', 'Budget-Friendly'),
        ('medium', 'Mid-Range'),
        ('high', 'Premium'),
    ]
    
    SIZE_CHOICES = [
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ]
    
    id = models.AutoField(primary_key=True)
    session_key = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Core session data
    preferences = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Quick access fields
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, null=True, blank=True)
    style_preference = models.CharField(max_length=20, choices=STYLE_CHOICES, null=True, blank=True)
    budget_range = models.CharField(max_length=10, choices=BUDGET_CHOICES, null=True, blank=True)
    budget_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # New field
    room_size = models.CharField(max_length=10, choices=SIZE_CHOICES, null=True, blank=True)
    
    # Simple metrics
    total_interactions = models.PositiveIntegerField(default=0)
    completion_percentage = models.PositiveSmallIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'showroom_user_sessions'
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['last_activity']),
        ]
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"Session {self.id} - {self.room_type or 'Unknown'}"
    
    def save(self, *args, **kwargs):
        """Override save to update fields from preferences"""
        if self.preferences:
            self.room_type = self.preferences.get('room_type')
            self.style_preference = self.preferences.get('style')
            self.budget_range = self.preferences.get('budget_range')
            
            # Handle budget amount
            budget_amount = self.preferences.get('budget_amount')
            if budget_amount:
                try:
                    self.budget_amount = float(budget_amount)
                    # Auto-set budget_range based on amount and room_type
                    self.budget_range = self._categorize_budget()
                except (ValueError, TypeError):
                    pass
                    
            self.room_size = self.preferences.get('room_size')
            self.completion_percentage = self._calculate_completion()
        
        self.last_activity = timezone.now()
        super().save(*args, **kwargs)
    
    def _categorize_budget(self):
        """Automatically categorize budget based on amount and room type"""
        if not self.budget_amount or not self.room_type:
            return None
            
        amount = float(self.budget_amount)
        
        if self.room_type == 'kitchen':
            if amount < 15000:
                return 'low'
            elif amount <= 30000:
                return 'medium'
            else:
                return 'high'
        elif self.room_type == 'bathroom':
            if amount < 7000:
                return 'low'
            elif amount <= 25000:
                return 'medium'
            else:
                return 'high'
        
        return 'medium'  # Default
    
    def _calculate_completion(self):
        """Simple completion calculation"""
        if not self.preferences:
            return 0
        
        room_type = self.preferences.get('room_type')
        if room_type not in ['bathroom', 'kitchen']:
            return 10 if room_type else 0
        
        # Essential fields only
        essential_fields = ['room_type', 'style', 'room_size', 'budget_range']
        completed = sum(1 for field in essential_fields if self.preferences.get(field))
        
        return min(90, int((completed / len(essential_fields)) * 100))
    
    def is_expired(self, hours=24):
        """Check if session has expired"""
        from datetime import timedelta
        expiry_time = self.created_at + timedelta(hours=hours)
        return timezone.now() > expiry_time

class ChatInteraction(models.Model):
    """Simplified chat interaction model"""
    
    INTENT_CHOICES = [
        ('room_identification', 'Room Identification'),
        ('style_discussion', 'Style Discussion'),
        ('pricing_inquiry', 'Pricing Inquiry'),
        ('product_recommendation', 'Product Recommendation'),
        ('general_conversation', 'General Conversation'),
    ]
    
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='interactions')
    
    user_message = models.TextField()
    ai_response = models.TextField()
    intent = models.CharField(max_length=30, choices=INTENT_CHOICES, default='general_conversation')
    extracted_preferences = models.JSONField(default=dict, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'showroom_chat_interactions'
        indexes = [
            models.Index(fields=['session', '-timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Interaction {self.id} - {self.intent}"
    
    def save(self, *args, **kwargs):
        """Update session interaction count"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            self.session.total_interactions = self.session.interactions.count()
            self.session.save(update_fields=['total_interactions', 'last_activity'])

# Simplified managers
class ActiveSessionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

UserSession.add_to_class('active', ActiveSessionManager())