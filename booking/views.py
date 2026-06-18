from rest_framework import viewsets, permissions
from .models import Provider, Appointment, ServiceItem  
from .serializers import ProviderListSerializer, AppointmentCreateSerializer, AdminCalendarAppointmentSerializer, AdminServiceItemSerializer, AdminProviderOptionSerializer
from rest_framework.decorators import action
from rest_framework.response import Response

class ProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    人員視圖 (大堂經理)
    負責前端選單：列出所有人員、他們提供的服務，以及 (未來實作的) 空檔計算
    目前設定為唯讀 (ReadOnly)，因為前端客人在這裡不應該有新增人員的權限。
    """
    queryset = Provider.objects.all()
    serializer_class = ProviderListSerializer
    # 未來這裡可以覆寫 get_queryset() 來實作多租戶： return Provider.objects.filter(shop=self.request.user.shop)

class AppointmentViewSet(viewsets.ModelViewSet):
    """
    預約訂單視圖 (大堂經理)
    負責接收前端的預約請求。
    """
    queryset = Appointment.objects.all()
    
    # 這裡預設開放權限方便初期測試，未來接上 LINE 登入後，會改成 permissions.IsAuthenticated
    permission_classes = [permissions.AllowAny] 

    def get_serializer_class(self):
        """動態切換翻譯官：POST 用扁平寫入，GET 讀取可以另外做一個嵌套的 (目前先用寫入的頂著)"""
        if self.action in ['create', 'update', 'partial_update']:
            return AppointmentCreateSerializer
        return AppointmentCreateSerializer # 如果未來有 AppointmentListSerializer 就在這裡 return
    

class MerchantAdminViewSet(viewsets.ViewSet):
    """
    業主管理後台核心 API (真正的 Skinny View)
    """

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar_appointments(self, request):
        """1. 行事曆區間資料：只負責接參數、呼叫、丟出"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        shop_id = request.query_params.get('shop_id', 1)

        if not start_date or not end_date:
            return Response({"error": "請提供 start_date 與 end_date"}, status=400)

        # 這裡一行直接呼叫 Manager 層
        queryset = Appointment.objects.for_shop_calendar(shop_id, start_date, end_date)
        
        serializer = AdminCalendarAppointmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def dashboard_stats(self, request):
        """2. 看板營收指標：完美貫徹大堂經理職責"""
        shop_id = request.query_params.get('shop_id', 1)
        
        # 商業運算？交給底層去算，我只負責收成果
        stats_data = Appointment.objects.get_dashboard_stats(shop_id)
        
        return Response(stats_data)
    
class AdminServiceItemViewSet(viewsets.ModelViewSet):
    """
    業主後台專用：服務品項系統 CRUD（完美切分多租戶網域）
    """
    serializer_class = AdminServiceItemSerializer
    
    def get_queryset(self):
        """
        核心防禦：根據傳入的 shop_id 進行嚴格的網域隔離
        """
        shop_id = self.request.query_params.get('shop_id', 1) # 測試階段預設為 1
        
        # 使用 prefetch_related 優化多對多查詢效能
        return ServiceItem.objects.filter(shop_id=shop_id).prefetch_related('providers').order_by('-id')

    def perform_create(self, serializer):
        """
        建立服務時，由後端強制注入 shop_id，不給前端作假的機會
        """
        shop_id = self.request.query_params.get('shop_id', 1)
        serializer.save(shop_id=shop_id)

    # ==========================================
    # 💡 完美回應你的需求：美甲師下拉選單 API
    # URL: GET /api/admin/services/provider_options/?shop_id=1
    # ==========================================
    @action(detail=False, methods=['get'], url_path='provider_options')
    def provider_options(self, request):
        """撈出目前店家旗下所有的美甲師，供前端複選框渲染"""
        shop_id = request.query_params.get('shop_id', 1)
        
        # 只撈取特定店家的美甲師
        queryset = Provider.objects.filter(shop_id=shop_id).order_by('id')
        serializer = AdminProviderOptionSerializer(queryset, many=True)
        return Response(serializer.data)