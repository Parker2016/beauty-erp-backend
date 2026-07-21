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
    # 💡 建議將價格類型 (price_type) 與是否為加購 (is_addon) 也放進列表顯示
    list_display = ('id', 'name', 'price', 'price_type', 'duration_minutes', 'is_addon', 'shop')
    list_filter = ('shop', 'is_addon', 'price_type')
    search_fields = ('name',)
    
    # 雙框選單：選擇提供此服務的美甲師
    filter_horizontal = ('providers',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    # 💡 多對多欄位不能直接寫進 list_display，需透過自訂函式 (get_services / get_addons) 轉為字串
    list_display = (
        'id', 'customer', 'get_services', 'get_addons', 
        'start_time', 'final_price', 'status', 'shop'
    )
    list_filter = ('status', 'shop', 'start_time')
    search_fields = ('customer__name', 'customer__phone', 'id')
    raw_id_fields = ('customer', 'provider') # 顧客跟美甲師數量多時，改用搜尋框載入更順暢
    
    # 💡 核心重點：主服務與加購項目都升級為漂亮的「左右雙框選單」
    filter_horizontal = ('services', 'addons')

    # 🛠️ 輔助函式：將多對多主服務拼接為可讀字串，顯示於列表頁
    def get_services(self, obj):
        services = obj.services.all()
        return ", ".join([s.name for s in services]) if services else "無主服務"
    get_services.short_description = "主服務項目" # 後台表頭顯示名稱

    # 🛠️ 輔助函式：將多對多加購項拼接為可讀字串
    def get_addons(self, obj):
        addons = obj.addons.all()
        return ", ".join([a.name for a in addons]) if addons else "無加購"
    get_addons.short_description = "追加項目"

@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'created_at')