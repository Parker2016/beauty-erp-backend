from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProviderViewSet, AppointmentViewSet, MerchantAdminViewSet, AdminServiceItemViewSet

# 建立路由器
router = DefaultRouter()

# 註冊我們的 ViewSet
router.register(r'providers', ProviderViewSet, basename='provider')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'admin', MerchantAdminViewSet, basename='merchant-admin')
router.register(r'admin/services', AdminServiceItemViewSet, basename='admin-services')

# 所有的 API 路徑都會自動被 router 產生
urlpatterns = [
    path('', include(router.urls)),
]