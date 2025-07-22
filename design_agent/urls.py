from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.GenerateDesignView.as_view(), name='generate_design'),
    path('details/<int:design_id>/', views.DesignDetailsView.as_view(), name='design_details'),
    path('export-pdf/<int:design_id>/', views.ExportPDFView.as_view(), name='export_pdf'),
    path('templates/', views.TemplatesView.as_view(), name='templates'),
]

