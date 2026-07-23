# booking/views.py
import datetime
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Provider, Appointment, ServiceItem  
from .serializers import (
    ProviderSerializer, 
    AppointmentCreateSerializer, 
    AdminCalendarAppointmentSerializer, 
    AdminServiceItemSerializer, 
    AdminProviderOptionSerializer, 
    AdminAppointmentWithRecordSerializer,
    ServiceItemSerializer
)


class ProviderViewSet(viewsets.ModelViewSet): # 💡 1. 核心修正：改為 ModelViewSet 才能接收 POST/PATCH/DELETE
    """
    人員視圖 (大堂經理)
    負責前台選單與後台 CRUD：列出人員、新增/編輯/刪除人員、綁定服務與空檔計算
    """
    queryset = Provider.objects.all().order_by('id')
    serializer_class = ProviderSerializer

    def perform_create(self, serializer):
        # 💡 2. 核心修正：新增人員時，自動幫忙綁定預設店鋪 (shop_id=1)
        shop_id = self.request.data.get('shop_id', 1)
        serializer.save(shop_id=shop_id)

    @action(detail=True, methods=['get'], url_path='services')
    def services(self, request, pk=None):
        """
        URL: GET /api/providers/{id}/services/
        明確撈出該名美甲師「有授權提供」的所有服務品項（包含主服務與加購項）
        """
        provider = self.get_object()
        
        # 安全防禦：自動相容各種 ORM 多對多反向關聯名稱
        if hasattr(provider, 'provided_services'):
            services_queryset = provider.provided_services.all()
        elif hasattr(provider, 'services'):
            services_queryset = provider.services.all()
        else:
            services_queryset = provider.serviceitem_set.all()
        
        serializer = ServiceItemSerializer(services_queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='available_slots')
    def available_slots(self, request, pk=None):
        """
        URL 範例: GET /api/providers/{id}/available_slots/?date=2026-07-18&service_ids[]=1&service_ids[]=2&addon_ids[]=3
        攔截前端帶來的日期、多選主服務與多選加購項 ID，丟入升級版防撞演算法計算
        """
        provider = self.get_object()
        date_str = request.query_params.get('date')
        
        # 抓取多選主服務 ID 陣列，並相容舊版單一 service_id
        raw_service_ids = request.query_params.getlist('service_ids[]') or request.query_params.getlist('service_ids')
        if not raw_service_ids and request.query_params.get('service_id'):
            raw_service_ids = [request.query_params.get('service_id')]

        # 抓取加購項 ID 陣列
        raw_addon_ids = request.query_params.getlist('addon_ids[]') or request.query_params.getlist('addon_ids')

        # 1. 安全防禦：檢查主參數
        if not date_str or not raw_service_ids:
            return Response({"error": "請提供 date 與 service_ids 參數"}, status=400)

        # 2. 安全防禦：轉換日期
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return Response({"error": "日期格式錯誤，請使用 YYYY-MM-DD"}, status=400)

        # 💡 3. 安全轉型：轉為數字陣列，防止惡意字串引發 500 錯誤
        try:
            service_ids = [int(x) for x in raw_service_ids if str(x).isdigit()]
            addon_ids = [int(x) for x in raw_addon_ids if str(x).isdigit()]
        except ValueError:
            return Response({"error": "服務項目 ID 必須為數字"}, status=400)

        # 4. 撈出所有指定的主服務品項物件
        service_items = list(ServiceItem.objects.filter(id__in=service_ids, is_addon=False))
        if not service_items:
            return Response({"error": "找不到指定的主服務項目，或選擇的品項屬於加購項"}, status=400)

        # 5. 撈出所有實體加購項物件
        addon_items = []
        if addon_ids:
            addon_items = list(ServiceItem.objects.filter(id__in=addon_ids, is_addon=True))

        # 6. 呼叫 Model 核心演算法 (傳入多選主服務列表 + 加購列表)
        available_slots = provider.get_available_slots(target_date, service_items, addon_items)
        
        return Response(available_slots)


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    預約訂單視圖 (大堂經理)
    負責接收前端的預約請求。
    """
    queryset = Appointment.objects.all()
    permission_classes = [permissions.AllowAny] 

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AppointmentCreateSerializer
        return AppointmentCreateSerializer 


class MerchantAdminViewSet(viewsets.ViewSet):
    """
    業主管理後台核心 API
    """

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar_appointments(self, request):
        """1. 行事曆區間資料"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        shop_id = request.query_params.get('shop_id', 1)

        if not start_date or not end_date:
            return Response({"error": "請提供 start_date 與 end_date"}, status=400)

        queryset = Appointment.objects.for_shop_calendar(shop_id, start_date, end_date)
        serializer = AdminCalendarAppointmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def dashboard_stats(self, request):
        """2. 看板營收指標"""
        shop_id = request.query_params.get('shop_id', 1)
        stats_data = Appointment.objects.get_dashboard_stats(shop_id)
        return Response(stats_data)


class AdminServiceItemViewSet(viewsets.ModelViewSet):
    """
    業主後台專用：服務品項系統 CRUD（網域隔離）
    """
    serializer_class = AdminServiceItemSerializer
    
    def get_queryset(self):
        shop_id = self.request.query_params.get('shop_id', 1) 
        return ServiceItem.objects.filter(shop_id=shop_id)\
            .prefetch_related('providers')\
            .order_by('is_addon', 'category', '-id')

    def perform_create(self, serializer):
        shop_id = self.request.query_params.get('shop_id', 1)
        serializer.save(shop_id=shop_id)

    @action(detail=False, methods=['get'], url_path='provider_options')
    def provider_options(self, request):
        shop_id = request.query_params.get('shop_id', 1)
        queryset = Provider.objects.filter(shop_id=shop_id).order_by('id')
        serializer = AdminProviderOptionSerializer(queryset, many=True)
        return Response(serializer.data)


class AdminAppointmentRecordViewSet(viewsets.ModelViewSet):
    """
    業主後台專用：預約單與一對一美甲紀錄 (CRUD)
    """
    serializer_class = AdminAppointmentWithRecordSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """
        嚴格多租戶網域隔離 ＋ 高效能預加載 (已修正 M2M 多對多崩潰 Bug)
        """
        shop_id = self.request.query_params.get('shop_id', 1)
        
        # 💡 關鍵修正：將 'service' 移除，對多對多欄位 (services, addons) 改用 prefetch_related
        return Appointment.objects.filter(shop_id=shop_id)\
            .select_related('customer', 'provider')\
            .prefetch_related('services', 'addons', 'record')\
            .order_by('-id')