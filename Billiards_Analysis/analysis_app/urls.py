from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_image, name='upload_image'),
    path('analysis/<int:analysis_id>/', views.analyze_view, name='analysis_view'),
    path('process/<int:analysis_id>/', views.process_analysis, name='process_analysis'),
]