from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import (
    Shop, Customer, Provider, ServiceItem, Appointment, ServiceRecord,
    DesignPriceItem, AppointmentDesignQuote, AppointmentDesignItem
)

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
    list_display = ('id', 'name', 'price', 'price_type', 'duration_minutes', 'is_addon', 'shop')
    list_filter = ('shop', 'is_addon', 'price_type')
    search_fields = ('name',)
    filter_horizontal = ('providers',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'get_services', 'get_addons', 
        'start_time', 'final_price', 'status', 'shop'
    )
    list_filter = ('status', 'shop', 'start_time')
    search_fields = ('customer__name', 'customer__phone', 'id')
    raw_id_fields = ('customer', 'provider')
    filter_horizontal = ('services', 'addons')

    def get_services(self, obj):
        services = obj.services.all()
        return ", ".join([s.name for s in services]) if services else "無主服務"
    get_services.short_description = "主服務項目"

    def get_addons(self, obj):
        addons = obj.addons.all()
        return ", ".join([a.name for a in addons]) if addons else "無加購"
    get_addons.short_description = "追加項目"

@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'created_at')

# ==========================================
# 🎨 1. 定義 Excel 與 Model 的對應關係 (Resource)
# ==========================================
class DesignPriceItemResource(resources.ModelResource):
    class Meta:
        model = DesignPriceItem
        # 決定 Excel 要匯入哪些欄位 (請與 Excel 的表頭名稱一致)
        fields = ('id', 'shop', 'category', 'name', 'price', 'sort_order', 'is_active')
        import_id_fields = ('id',) # 依據 id 來判斷是新增還是更新

# ==========================================
# 🎨 1. 設計款價目表維護 (Design Price Menu)
# ==========================================
@admin.register(DesignPriceItem)
class DesignPriceItemAdmin(ImportExportModelAdmin):
    resource_class = DesignPriceItemResource
    list_display = ('id', 'category', 'name', 'price', 'sort_order', 'is_active', 'shop')
    list_filter = ('category', 'is_active', 'shop')
    search_fields = ('name',)
    list_editable = ('price', 'sort_order', 'is_active')  # 讓店長可以直接在列表頁快速改價格


# ==========================================
# 🧾 2. 結帳快照管理 (Quote Snapshot)
# ==========================================
class AppointmentDesignItemInline(admin.TabularInline):
    """將結帳明細作為內嵌表單，方便在同一個頁面新增"""
    model = AppointmentDesignItem
    extra = 1  # 預設多留 1 個空行

@admin.register(AppointmentDesignQuote)
class AppointmentDesignQuoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'appointment', 'subtotal', 'deposit', 'discount', 'total_amount', 'created_at')
    search_fields = ('appointment__customer__name',)
    raw_id_fields = ('appointment',)  # 預約單很多時，用搜尋放大鏡比較好找
    inlines = [AppointmentDesignItemInline]  # 💡 載入內嵌的明細表單