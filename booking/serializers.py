from rest_framework import serializers
from django.utils import timezone
import datetime
from .models import Shop, Customer, Provider, ServiceItem, Appointment, ServiceRecord, DesignPriceItem, AppointmentDesignQuote, AppointmentDesignItem

# ==========================================
# GET 專用：讀取嵌套 (Read Nested)
# ==========================================

class ServiceItemSerializer(serializers.ModelSerializer):
    """服務項目，負責在 Provider 中被嵌套顯示"""
    class Meta:
        model = ServiceItem
        fields = [
            'id', 
            'name', 
            'duration_minutes', 
            'price', 
            'description',
            'price_type',
            'is_addon',
            'category'
        ]

class ProviderSerializer(serializers.ModelSerializer):
    """人員序列化器 (支援 CRUD 完整欄位)"""
    shop_id = serializers.IntegerField(write_only=True, required=False, default=1)

    class Meta:
        model = Provider
        fields = ['id', 'name', 'is_manager', 'shop_id']

# ==========================================
# POST 專用：寫入扁平 (Write Flat) 與防超賣驗證
# ==========================================

class AppointmentCreateSerializer(serializers.ModelSerializer):
    """
    前端建立預約專用（完全體：支援多選主服務 ＋ 工時自動加總 ＋ 金額自動預算）
    """
    provider_id = serializers.IntegerField(write_only=True)
    customer_id = serializers.IntegerField(write_only=True) 
    
    # 💡 1. 將單選 service_id 改為多選 service_ids 列表
    service_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    
    addon_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        write_only=True, 
        required=False, 
        default=list
    )

    class Meta:
        model = Appointment
        # 💡 將 service_id 替換為 service_ids
        fields = [
            'id', 'provider_id', 'service_ids', 'addon_ids', 'customer_id', 
            'start_time', 'memo', 'status', 'final_price'
        ]
        read_only_fields = ['id', 'status', 'final_price'] # 🔒 安全鎖定

    def validate(self, data):
        """
        Serializer 的靈魂：防呆、時間防撞，與「多服務工時/金額自動預算」邏輯
        """
        # 1. 驗證服務項目不能為空
        service_ids = data.get('service_ids', [])
        if not service_ids:
            raise serializers.ValidationError({"service_ids": "請至少選擇一項主服務項目。"})

        try:
            provider = Provider.objects.get(id=data['provider_id'])
            customer = Customer.objects.get(id=data['customer_id'])
        except (Provider.DoesNotExist, Customer.DoesNotExist):
            raise serializers.ValidationError("傳入的 ID 不存在 (人員或會員)")

        # 撈出並驗證多選主服務項目
        services = list(ServiceItem.objects.filter(id__in=service_ids, is_addon=False))
        if len(services) != len(service_ids):
            raise serializers.ValidationError({"service_ids": "部分主服務項目不存在或為加購品項。"})

        data['shop'] = provider.shop

        # 撈出並驗證加購項
        addon_ids = data.get('addon_ids', [])
        addon_items = list(ServiceItem.objects.filter(id__in=addon_ids, is_addon=True))
        if len(addon_items) != len(addon_ids):
            raise serializers.ValidationError({"addon_ids": "部分加購項目不存在或非合法加購品項。"})

        # 2. 自動推導多項主服務 ＋ 所有加購項的實質總工時
        total_duration_minutes = sum(s.duration_minutes for s in services) + sum(addon.duration_minutes for addon in addon_items)
        start_time = data['start_time']
        end_time = start_time + datetime.timedelta(minutes=total_duration_minutes)

        # 3. 終極防超賣檢查 (以總工時計算出來的 end_time 進行碰撞檢查)
        overlapping = Appointment.objects.filter(
            provider=provider,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['PENDING', 'CONFIRMED']
        ).exists()

        if overlapping:
            raise serializers.ValidationError({"start_time": "手腳太慢啦！這個時段剛剛被其他人預約了。"})

        # 4. 自動預算本次實收金額 (final_price)
        # 🎯 只要選擇的主服務中有任何一項屬於設計款/現場報價 ('QUOTE')，即保持 None/Null
        has_quote_service = any(getattr(s, 'price_type', None) == 'QUOTE' for s in services)

        if has_quote_service:
            data['final_price'] = None
        else:
            # 🎯 否則自動將「所有主服務金額 ＋ 所有加購金額」加總作為預設金額
            total_price = sum(s.price for s in services) + sum(addon.price for addon in addon_items)
            data['final_price'] = total_price

        # 5. 封裝數據下放給 create()
        data['end_time'] = end_time
        data['provider'] = provider
        data['customer'] = customer
        data['services_to_save'] = services
        data['addons_to_save'] = addon_items 

        data.pop('provider_id')
        data.pop('service_ids')
        data.pop('customer_id')
        data.pop('addon_ids', None)

        return data

    def create(self, validated_data):
        services = validated_data.pop('services_to_save', [])
        addon_items = validated_data.pop('addons_to_save', [])
        
        # 建立預約單主體
        appointment = Appointment.objects.create(**validated_data)
        
        # 💡 設定多對多關聯：主服務與加購項
        if services:
            appointment.services.set(services)
        if addon_items:
            appointment.addons.set(addon_items)
            
        return appointment
    
class AdminCalendarCustomerSerializer(serializers.ModelSerializer):
    """管理端專用：客人基本資料"""
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone']

class AdminCalendarServiceItemSerializer(serializers.ModelSerializer):
    """管理端專用：服務項目摘要"""
    class Meta:
        model = ServiceItem
        fields = ['id', 'name', 'price', 'duration_minutes']

class AdminCalendarAppointmentSerializer(serializers.ModelSerializer):
    """
    管理端行事曆專用：高密度嵌套讀取
    """
    customer = AdminCalendarCustomerSerializer(read_only=True)
    services = AdminCalendarServiceItemSerializer(many=True, read_only=True)
    addons = AdminCalendarServiceItemSerializer(many=True, read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'customer', 'services', 'provider_name',
            'start_time', 'end_time', 'status', 'memo',
            'addons', 'final_price'
        ]

class AdminProviderOptionSerializer(serializers.ModelSerializer):
    """管理後台下拉選單/複選框專用：極輕量美甲師資訊"""
    class Meta:
        model = Provider
        fields = ['id', 'name']

class AdminServiceItemSerializer(serializers.ModelSerializer):
    """
    管理後台服務品項 CRUD 專用 Serializer (完全體：支援彈性計價與加購分類)
    """
    # 讀取時：嵌套美甲師基本物件列表
    providers = AdminProviderOptionSerializer(many=True, read_only=True)
    
    # 寫入時：接收純數字陣列 (例如 [1, 2])，不與 Model 欄位直接衝突
    provider_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="傳入要綁定的美甲師 ID 陣列"
    )

    class Meta:
        model = ServiceItem
        fields = [
            'id', 'name', 'duration_minutes', 'price', 
            'description', 'providers', 'provider_ids',
            # 💡 核心補強：釋放新欄位給後台管理介面進行寫入與修改
            'price_type',  # 💸 FIXED (固定) / STARTING (起價) / QUOTE (現場報價)
            'is_addon',    # ➕ True (加購項目) / False (主服務)
            'category'     # 💅 HAND (手部) / FOOT (足部) / PURE_REMOVAL (純卸甲) / ADDON (加購)
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        # 1. 剝離出多對多的美甲師 ID 陣列
        provider_ids = validated_data.pop('provider_ids', [])
        
        # 2. 建立服務品項本體 (validated_data 此時會自動包含新加入的 price_type, is_addon, category)
        service_item = ServiceItem.objects.create(**validated_data)
        
        # 3. 同步寫入多對多關聯資料庫
        if provider_ids:
            providers = Provider.objects.filter(id__in=provider_ids, shop=service_item.shop)
            service_item.providers.set(providers)
            
        return service_item

    def update(self, instance, validated_data):
        # 1. 剝離出多對多的美甲師 ID 陣列
        provider_ids = validated_data.pop('provider_ids', None)
        
        # 2. 更新服務品項本體欄位 (super().update 會自動處理常規欄位的覆蓋)
        instance = super().update(instance, validated_data)
        
        # 3. 如果前端有傳這個陣列，就覆蓋更新多對多關聯
        if provider_ids is not None:
            providers = Provider.objects.filter(id__in=provider_ids, shop=instance.shop)
            instance.providers.set(providers)
            
        return instance

class AdminServiceRecordSerializer(serializers.ModelSerializer):
    """施作紀錄的扁平轉譯器"""
    id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = ServiceRecord
        # 對齊前端傳入的材料色號與作品照網址
        fields = ['id', 'materials_note', 'image_url']


class AdminAppointmentWithRecordSerializer(serializers.ModelSerializer):
    """
    業主後台專用：預約狀態、多選主服務與施作紀錄的「一對一/多對多聯合寫入」序列化器 (完全體對齊版)
    """
    record = AdminServiceRecordSerializer(required=False, allow_null=True)
    
    # 💡 1. 補齊：嵌套 customer 物件 (包含 id, name, phone)，讓 Modal 能顯示顧客電話
    customer = AdminCalendarCustomerSerializer(read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    # 💡 2. 補齊：擔當美甲師名稱
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    # 💡 3. 嵌套多選服務與加購項目 (採用帶有 price, duration_minutes 的 ServiceItemSerializer)
    services = ServiceItemSerializer(many=True, read_only=True)
    addons = ServiceItemSerializer(many=True, read_only=True)

    # 💡 4. 多對多主服務：接收前端 Modal 傳入的 ID 陣列 (例如 service_ids: [1, 2])
    service_ids = serializers.PrimaryKeyRelatedField(
        queryset=ServiceItem.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source='services'
    )

    class Meta:
        model = Appointment
        # 💡 全面對齊 AdminCalendarAppointmentSerializer 所需的所有完整欄位
        fields = [
            'id', 
            'customer',        # 包含 name, phone 的顧客物件
            'customer_name',   # 平鋪版顧客姓名 (備用相容)
            'provider_name',   # 擔當美甲師名稱
            'services',        # 多選主服務陣列 (含 price, duration_minutes)
            'service_ids',     # 寫入用：服務 ID 陣列
            'addons',          # 多選加購陣列 (含 price, duration_minutes)
            'start_time',      # 開始時間
            'status',          # 預約狀態
            'memo',            # 客戶留言備註
            'final_price',     # 現場結帳實收金額
            'record'           # 1:1 施作紀錄 (色號、款式照片)
        ]

    def update(self, instance, validated_data):
        # 抽出多對多 services 與一對一 record 的資料
        services_data = validated_data.pop('services', None)
        record_data = validated_data.pop('record', None)

        # 1. 更新 Appointment 本身的基本欄位 (包含 status, start_time, final_price)
        instance.status = validated_data.get('status', instance.status)
        instance.start_time = validated_data.get('start_time', instance.start_time)
        instance.end_time = validated_data.get('end_time', instance.end_time)
        instance.memo = validated_data.get('memo', instance.memo)
        instance.final_price = validated_data.get('final_price', instance.final_price)
        instance.save()

        # 2. 更新多對多主服務項目 (ManyToManyField)
        if services_data is not None:
            instance.services.set(services_data)  # 用 .set() 覆蓋全新的服務項目組合

        # 3. 處理一對一 ServiceRecord 的生命週期
        if record_data is not None:
            materials_note = record_data.get('materials_note', '')
            image_url = record_data.get('image_url', '')

            ServiceRecord.objects.update_or_create(
                appointment=instance,
                defaults={
                    'materials_note': materials_note,
                    'image_url': image_url
                }
            )

        return instance

# ==========================================
# 1. 價目表模板管理 (Shop Settings)
# ==========================================
class DesignPriceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignPriceItem
        fields = ['id', 'category', 'name', 'price', 'sort_order', 'is_active']

# ==========================================
# 2. 結帳明細快照 (Quote Items)
# ==========================================
class AppointmentDesignItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentDesignItem
        # 排除 quote，因為寫入時會由父層 (Quote) 自動綁定
        exclude = ['quote'] 

# ==========================================
# 3. 結帳總表快照 (Quote Master)
# ==========================================
class AppointmentDesignQuoteSerializer(serializers.ModelSerializer):
    # 💡 宣告嵌套的明細序列化器，many=True 代表這是一個陣列
    items = AppointmentDesignItemSerializer(many=True)

    class Meta:
        model = AppointmentDesignQuote
        fields = [
            'id', 'appointment', 'deposit', 'discount', 
            'subtotal', 'total_amount', 'formatted_receipt', 'items'
        ]
        # appointment 設為唯讀，由 URL 或 View 邏輯中帶入，防止被惡意竄改
        read_only_fields = ['appointment']

    def update(self, instance, validated_data):
        """
        處理覆寫/更新結帳快照 (Update)
        """
        # 1. 將 items 陣列從驗證資料中抽離出來
        items_data = validated_data.pop('items', [])

        # 2. 更新主表 Quote 的基本欄位 (金額、明細文字)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 3. 處理快證明細：先清空舊的明細，再重新建立新的 (Snapshot 特性)
        instance.items.all().delete()
        for item_data in items_data:
            AppointmentDesignItem.objects.create(quote=instance, **item_data)

        return instance

    def create(self, validated_data):
        """
        處理首次建立結帳快照 (Create)
        """
        items_data = validated_data.pop('items', [])
        # 從 context 取得綁定的預約單 (View 裡面會傳入)
        appointment = self.context['appointment']
        
        # 建立主表
        quote = AppointmentDesignQuote.objects.create(appointment=appointment, **validated_data)
        
        # 建立明細
        for item_data in items_data:
            AppointmentDesignItem.objects.create(quote=quote, **item_data)
            
        return quote