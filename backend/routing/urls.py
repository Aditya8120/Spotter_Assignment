from django.urls import path
from .views import health_check, plan_routes

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('routes/', plan_routes, name='plan_routes'),
]

