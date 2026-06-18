from rest_framework import serializers
from django.utils import timezone
import datetime
from .models import Shop, Customer, Provider, ServiceItem, Appointment

# ==========================================
# GET 專用：讀取嵌套 (Read Nested)
# ==========================================

class ServiceItemSerializer(serializers.ModelSerializer):
    """服務項目，負責在 Provider 中被嵌套顯示"""
    class Meta:
        model = ServiceItem
        # 嚴格禁止使用 '__all__'，明確列出前端需要的欄位
        fields = ['id', 'name', 'duration_minutes', 'price', 'description']

class ProviderListSerializer(serializers.ModelSerializer):
    """人員列表，同時夾帶該人員能提供的服務"""
    # 這裡的 source 對應 Model 中 ManyToManyField 的 related_name
    services = ServiceItemSerializer(source='provided_services', many=True, read_only=True)
    
    class Meta:
        model = Provider
        fields = ['id', 'name', 'is_manager', 'services']


# ==========================================
# POST 專用：寫入扁平 (Write Flat) 與防超賣驗證
# ==========================================

class AppointmentCreateSerializer(serializers.ModelSerializer):
    """
    前端建立預約專用。
    只接收 ID 與開始時間，結束時間由後端強制推導，杜絕前端假造資料。
    """
    provider_id = serializers.IntegerField(write_only=True)
    service_id = serializers.IntegerField(write_only=True)
    customer_id = serializers.IntegerField(write_only=True) 
    # 未來導入 LINE 登入後，customer_id 可以改由 View 層從 request.user 自動提取，這裡先保留欄位

    class Meta:
        model = Appointment
        fields = [
            'id', 'provider_id', 'service_id', 'customer_id', 
            'start_time', 'memo', 'status'
        ]
        read_only_fields = ['id', 'status'] # status 預設會是 PENDING，不讓前端傳入

    def validate(self, data):
        """
        Serializer 的靈魂：防呆與商業邏輯驗證
        """
        try:
            provider = Provider.objects.get(id=data['provider_id'])
            service = ServiceItem.objects.get(id=data['service_id'])
            customer = Customer.objects.get(id=data['customer_id'])
        except (Provider.DoesNotExist, ServiceItem.DoesNotExist, Customer.DoesNotExist):
            raise serializers.ValidationError("傳入的 ID 不存在 (人員、服務或會員)")

        data['shop'] = provider.shop

        # 1. 自動推導 end_time
        start_time = data['start_time']
        end_time = start_time + datetime.timedelta(minutes=service.duration_minutes)

        # 2. 終極防超賣檢查 (Double Check)
        # 雖然前端已經透過 get_available_slots 過濾了，但送出瞬間可能會有併發(Concurrency)
        overlapping = Appointment.objects.filter(
            provider=provider,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['PENDING', 'CONFIRMED']
        ).exists()

        if overlapping:
            raise serializers.ValidationError({"start_time": "手腳太慢啦！這個時段剛剛被其他人預約了，請重新選擇。"})

        # 3. 把物件塞回 data，供 View 執行 .save() 時使用
        data['end_time'] = end_time
        data['provider'] = provider
        data['service'] = service
        data['customer'] = customer
        
        # 為了不讓 Django ORM 報錯，把純 ID 欄位清掉
        data.pop('provider_id')
        data.pop('service_id')
        data.pop('customer_id')

        return data
    
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
    service = AdminCalendarServiceItemSerializer(read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'customer', 'service', 'provider_name',
            'start_time', 'end_time', 'status', 'memo'
        ]

class AdminProviderOptionSerializer(serializers.ModelSerializer):
    """管理後台下拉選單/複選框專用：極輕量美甲師資訊"""
    class Meta:
        model = Provider
        fields = ['id', 'name']

class AdminServiceItemSerializer(serializers.ModelSerializer):
    """
    管理後台服務品項 CRUD 專用 Serializer
    """
    # 讀取時：嵌套美甲師物件列表
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
            'description', 'providers', 'provider_ids'
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        # 1. 剝離出多對多的美甲師 ID 陣列
        provider_ids = validated_data.pop('provider_ids', [])
        
        # 2. 建立服務品項本體 (shop_id 會由 View 層在呼叫 save() 時注入)
        service_item = ServiceItem.objects.create(**validated_data)
        
        # 3. 同步寫入多對多關聯資料庫
        if provider_ids:
            providers = Provider.objects.filter(id__in=provider_ids, shop=service_item.shop)
            service_item.providers.set(providers)
            
        return service_item

    def update(self, instance, validated_data):
        # 1. 剝離出多對多的美甲師 ID 陣列
        provider_ids = validated_data.pop('provider_ids', None)
        
        # 2. 更新服務品項本體欄位
        instance = super().update(instance, validated_data)
        
        # 3. 如果前端有傳這個陣列，就覆蓋更新多對多關聯
        if provider_ids is not None:
            providers = Provider.objects.filter(id__in=provider_ids, shop=instance.shop)
            instance.providers.set(providers)
            
        return instance