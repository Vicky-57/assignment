from django.db import models
from products.models import Product
from showroom_agent.models import UserSession

class LayoutTemplate(models.Model):
    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=50)
    style = models.CharField(max_length=50)
    image = models.ImageField(upload_to='layout_templates/', null=True, blank=True)
    dimensions = models.JSONField()  
    product_slots = models.JSONField()  
    template_description = models.TextField()
    color_palette = models.JSONField(null=True, blank=True, default=list)
    estimated_budget = models.JSONField(null=True, blank=True, default=dict)
    
    def __str__(self):
        return f"{self.name} - {self.room_type}"

class DesignRecommendation(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    layout_template = models.ForeignKey(LayoutTemplate, on_delete=models.CASCADE,null=True,blank=True)
    room_dimensions = models.JSONField()
    user_preferences = models.JSONField()
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    ai_reasoning = models.TextField(blank=True)
    dealer_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ProductRecommendation(models.Model):
    design = models.ForeignKey(DesignRecommendation, on_delete=models.CASCADE, related_name='product_recommendations')
    product = models.ForeignKey(Product, on_delete=models.CASCADE,null=True ,blank=True)
    quantity = models.PositiveIntegerField(default=1)
    slot_name = models.CharField(max_length=100)
    reasoning = models.TextField(blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
