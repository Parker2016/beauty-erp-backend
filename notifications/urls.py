from django.urls import path
from .views import line_webhook

urlpatterns = [
    path('line/webhook/', line_webhook, name='line_webhook'),
]