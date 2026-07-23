# booking/models.py (或你的 Manager 檔案)
import calendar
from datetime import datetime, time, timedelta
from django.db import models
from django.db.models import Sum, Count, Q
from django.utils import timezone

class AppointmentQuerySet(models.QuerySet):
    """
    將所有關於預約的「商業查詢邏輯」與「統計計算」高內聚在這裡
    """
    
    def for_shop_calendar(self, shop_id, start_date_str, end_date_str):
        """核心邏輯：過濾行事曆時間區間 (時區防禦安全版)"""
        start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # 💡 轉化為帶時區標籤的有感時間 (Aware Datetime)，瓦解 naive datetime 警告
        aware_start = timezone.make_aware(datetime.combine(start_d, time.min))
        aware_end = timezone.make_aware(datetime.combine(end_d, time.max))
        
        return self.filter(
            shop_id=shop_id,
            start_time__gte=aware_start,
            start_time__lte=aware_end
        ).select_related(
            'customer', 'provider'             # 💡 1. 移除 'service'，只留單對一外鍵
        ).prefetch_related(
            'services', 'addons'               # 💡 2. 將 'services' 加入多對多預加載
        ).order_by('start_time')

    def get_dashboard_stats(self, shop_id):
        """核心邏輯：計算營收與看板指標 (解決時區污染與漏算改價問題)"""
        # 修正時區：先轉換為專案設定的本地時間 (如 Asia/Taipei)
        local_now = timezone.localtime(timezone.now())
        
        # 精準切出本地時間的今日起訖點 (00:00:00.000 ~ 23:59:59.999)
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = local_now.replace(hour=23, minute=59, second=59, microsecond=999999)

        # 本週起訖（以週一為第一天）
        week_start = today_start - timedelta(days=today_start.weekday())
        # ✅ 已修正：修正 timedelta 欄位錯誤，改用 .replace() 設定一日之終
        week_end = (week_start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)

        # 本月起訖
        month_start = today_start.replace(day=1)
        _, last_day = calendar.monthrange(month_start.year, month_start.month) # 動態撈取當月最後一天
        month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

        # 納入計價的預約單狀態
        revenue_states = ['PENDING', 'CONFIRMED', 'COMPLETED']

        stats = self.filter(shop_id=shop_id).aggregate(
            today_revenue=Sum('final_price', filter=Q(start_time__gte=today_start, start_time__lte=today_end, status__in=revenue_states)),
            week_revenue=Sum('final_price', filter=Q(start_time__gte=week_start, start_time__lte=week_end, status__in=revenue_states)),
            month_revenue=Sum('final_price', filter=Q(start_time__gte=month_start, start_time__lte=month_end, status__in=revenue_states)),
            
            today_total_count=Count('id', filter=Q(start_time__gte=today_start, start_time__lte=today_end)),
            today_confirmed_count=Count('id', filter=Q(start_time__gte=today_start, start_time__lte=today_end, status='CONFIRMED')),
            today_pending_count=Count('id', filter=Q(start_time__gte=today_start, start_time__lte=today_end, status='PENDING'))
        )
        
        return {
            "revenue": {
                "today": int(stats['today_revenue'] or 0),
                "week": int(stats['week_revenue'] or 0),
                "month": int(stats['month_revenue'] or 0)
            },
            "today_counts": {
                "total": stats['today_total_count'] or 0,
                "confirmed": stats['today_confirmed_count'] or 0,
                "pending": stats['today_pending_count'] or 0
            }
        }