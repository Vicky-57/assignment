from django.db import models

class ProductCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    STYLE_CHOICES = [
        ('modern', 'Modern'),
        ('traditional', 'Traditional'),
        ('contemporary', 'Contemporary'),
        ('rustic', 'Rustic'),
        ('minimalist', 'Minimalist'),
        ('industrial', 'Industrial'),
    ]
    
    ROOM_TYPE_CHOICES = [
        ('living_room', 'Living Room'),
        ('bedroom', 'Bedroom'),
        ('kitchen', 'Kitchen'),
        ('dining_room', 'Dining Room'),
        ('bathroom', 'Bathroom'),
        ('office', 'Office'),
    ]
    
    #id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    style = models.CharField(max_length=100, choices=STYLE_CHOICES)
    material = models.CharField(max_length=100)
    finish = models.CharField(max_length=100)
    room_type = models.CharField(max_length=50, choices=ROOM_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    description = models.TextField()
    specifications = models.JSONField(null=True,blank=True)
    embedding_vector = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    @property
    def search_text(self):
        return f"{self.name} {self.style} {self.material} {self.finish} {self.description}"
