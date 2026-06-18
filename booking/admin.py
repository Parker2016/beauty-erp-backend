from django.contrib import admin
from .models import Shop, Customer, Provider, ServiceItem, Appointment, ServiceRecord

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'shop', 'created_at')
    search_fields = ('name', 'phone')

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_manager', 'shop')

@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_minutes', 'shop')
    # filter_horizontal 能讓你在後台選擇「提供此服務的人員」時，擁有一個很漂亮的雙框選單
    filter_horizontal = ('providers',) 

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'provider', 'service', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'provider', 'shop')
    date_hierarchy = 'start_time' # 加入按日期篩選的時間軸

@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'created_at')