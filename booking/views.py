# booking/views.py
import datetime
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Shop, Provider, ProviderShift, Appointment, ServiceItem, DesignPriceItem, AppointmentDesignQuote
from .serializers import (
    ProviderSerializer, ProviderShiftSerializer,
    AppointmentCreateSerializer, 
    AdminCalendarAppointmentSerializer, 
    AdminServiceItemSerializer, 
    AdminProviderOptionSerializer, 
    AdminAppointmentWithRecordSerializer,
    ServiceItemSerializer,
    DesignPriceItemSerializer, AppointmentDesignQuoteSerializer
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

class ProviderShiftViewSet(viewsets.ModelViewSet):
    queryset = ProviderShift.objects.all()
    serializer_class = ProviderShiftSerializer

    def get_queryset(self):
        queryset = ProviderShift.objects.all()
        provider_id = self.request.query_params.get('provider_id')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if provider_id and provider_id != 'all':
            queryset = queryset.filter(provider_id=provider_id)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset.order_by('date', 'provider_id')

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_save(self, request):
        """
        整月批次排班 / 單日調整端點（支援 break_times 休息時段）
        """
        data = request.data
        provider_id = data.get('provider_id')
        shifts_data = data.get('shifts', [])

        if not provider_id or not shifts_data:
            return Response({"error": "請提供 provider_id 與 shifts 資料陣列"}, status=status.HTTP_400_BAD_REQUEST)

        provider = get_object_or_404(Provider, id=provider_id)

        try:
            with transaction.atomic():
                for shift_item in shifts_data:
                    date_str = shift_item.get('date')
                    if not date_str:
                        continue

                    is_off = shift_item.get('is_off', False)
                    start_time = shift_item.get('start_time') if not is_off else None
                    end_time = shift_item.get('end_time') if not is_off else None
                    
                    # 💡 抓取前端傳來的休息時段清單（如果是公休則清空）
                    break_times = shift_item.get('break_times', []) if not is_off else []

                    # 有則更新 (Update)，無則新增 (Create)
                    ProviderShift.objects.update_or_create(
                        provider=provider,
                        date=date_str,
                        defaults={
                            'start_time': start_time,
                            'end_time': end_time,
                            'is_off': is_off,
                            'break_times': break_times  # 💡 寫入 JSON 欄位
                        }
                    )

            return Response({"message": "排班資料儲存成功"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"排班儲存失敗: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
        provider_id = request.query_params.get('provider_id') # 💡 抓取選定的美甲師 ID

        if not start_date or not end_date:
            return Response({"error": "請提供 start_date 與 end_date"}, status=400)

        queryset = Appointment.objects.for_shop_calendar(shop_id, start_date, end_date, provider_id)
        serializer = AdminCalendarAppointmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def dashboard_stats(self, request):
        """2. 看板營收指標"""
        shop_id = request.query_params.get('shop_id', 1)
        provider_id = request.query_params.get('provider_id') # 💡 抓取選定的美甲師 ID
        
        stats_data = Appointment.objects.get_dashboard_stats(shop_id, provider_id)
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

class DesignPriceItemViewSet(viewsets.ModelViewSet):
    """
    美甲店設計款菜單維護 API
    GET, POST, PUT, DELETE /api/admin/design-prices/
    """
    serializer_class = DesignPriceItemSerializer

    def get_queryset(self):
        # 依照前端帶入的 shop_id 進行過濾 (預設 1)
        shop_id = self.request.query_params.get('shop_id', 1)
        return DesignPriceItem.objects.filter(shop_id=shop_id).order_by('category', 'sort_order')

    def perform_create(self, serializer):
        # 新增時自動綁定店舖
        shop_id = self.request.query_params.get('shop_id', 1)
        serializer.save(shop_id=shop_id)

    # =========================================================================
    # 💡 新增：對應前端 batchUpdateDesignPrices 的批次處理端點
    # 對應路由: POST /api/admin/design-prices/batch/
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='batch')
    def batch_update(self, request):
        data = request.data
        shop_id = data.get('shop_id', 1)
        deleted_ids = data.get('deleted_ids', [])
        items_data = data.get('items', [])

        shop = get_object_or_404(Shop, id=shop_id)

        try:
            with transaction.atomic():
                # 1. 批次刪除
                if deleted_ids:
                    DesignPriceItem.objects.filter(shop=shop, id__in=deleted_ids).delete()

                # 2. 批次新增與更新
                for item in items_data:
                    item_id = item.get('id')
                    
                    if item_id:
                        # 更新已存在項目
                        try:
                            db_item = DesignPriceItem.objects.get(shop=shop, id=item_id)
                            db_item.category = item.get('category', db_item.category)
                            db_item.name = item.get('name', db_item.name)
                            db_item.price = item.get('price', db_item.price)
                            db_item.sort_order = item.get('sort_order', db_item.sort_order)
                            db_item.is_active = item.get('is_active', db_item.is_active)
                            db_item.save()
                        except DesignPriceItem.DoesNotExist:
                            continue 
                    else:
                        # 新增項目
                        if item.get('name') and item.get('category'):
                            DesignPriceItem.objects.create(
                                shop=shop,
                                category=item.get('category'),
                                name=item.get('name'),
                                price=item.get('price', 0),
                                sort_order=item.get('sort_order', 1),
                                is_active=item.get('is_active', True)
                            )

            return Response({'message': '批次更新成功'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': '批次更新失敗，請檢查資料格式'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AppointmentDesignQuoteViewSet(viewsets.ViewSet):
    """
    單一預約單的結帳快照 API 
    因為這與 Appointment 是一對一，用自訂 ViewSet 處理 Retrieve 與 Save 會更乾淨。
    """

    def retrieve(self, request, appointment_id=None):
        """
        取得特定預約單的結帳快照
        GET /api/admin/appointments/{appointment_id}/quote/
        """
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        try:
            quote = appointment.design_quote
            serializer = AppointmentDesignQuoteSerializer(quote)
            return Response(serializer.data)
        except AppointmentDesignQuote.DoesNotExist:
            # 如果這張單還沒有結帳紀錄，回傳 404 或空資料讓前端初始化
            return Response({"detail": "尚無結帳紀錄", "has_quote": False}, status=status.HTTP_404_NOT_FOUND)

    def save_quote(self, request, appointment_id=None):
        """
        新增或覆寫結帳快照 (使用 PUT 或 POST 皆可)
        PUT /api/admin/appointments/{appointment_id}/quote/
        """
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        # 檢查是否已有快照
        if hasattr(appointment, 'design_quote'):
            # 更新現有快照
            serializer = AppointmentDesignQuoteSerializer(
                appointment.design_quote, 
                data=request.data, 
                partial=True
            )
        else:
            # 建立新快照，並透過 context 把 appointment 傳進 Serializer
            serializer = AppointmentDesignQuoteSerializer(
                data=request.data, 
                context={'appointment': appointment}
            )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)