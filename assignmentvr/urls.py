from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from showroom_agent.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='home'),  # If using Option 1
    path('api/showroom/', include('showroom_agent.urls')),
    path('api/design/', include('design_agent.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
