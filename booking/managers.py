from django.db import models
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta

class AppointmentQuerySet(models.QuerySet):
    """
    將所有關於預約的「商業查詢邏輯」與「統計計算」高內聚在這裡
    """
    
    def for_shop_calendar(self, shop_id, start_date_str, end_date_str):
        """核心邏輯：過濾行事曆時間區間"""
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        return self.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('customer', 'service', 'provider').order_by('start_time')

    def get_dashboard_stats(self, shop_id):
        """核心邏輯：計算營收與看板看盤指標 (Fat Model/Manager 實作)"""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        revenue_states = ['PENDING', 'CONFIRMED', 'COMPLETED']
        today_end = today_start.replace(hour=23, minute=59, second=59)

        stats = self.filter(shop_id=shop_id).aggregate(
            today_revenue=Sum('service__price', filter=Q(start_time__gte=today_start, status__in=revenue_states)),
            week_revenue=Sum('service__price', filter=Q(start_time__gte=week_start, status__in=revenue_states)),
            month_revenue=Sum('service__price', filter=Q(start_time__gte=month_start, status__in=revenue_states)),
            
            today_total_count=Count('id', filter=Q(start_time__gte=today_start, start_time__lte=today_end)),
            today_confirmed_count=Count('id', filter=Q(start_time__gte=today_start, start_time__lte=today_end, status='CONFIRMED')),
            today_pending_count=Count('id', filter=Q(start_time__gte=today_start, start_time__lte=today_end, status='PENDING'))
        )
        
        # 格式化輸出，保持 Manager 的輸出乾淨
        return {
            "revenue": {
                "today": stats['today_revenue'] or 0,
                "week": stats['week_revenue'] or 0,
                "month": stats['month_revenue'] or 0
            },
            "today_counts": {
                "total": stats['today_total_count'] or 0,
                "confirmed": stats['today_confirmed_count'] or 0,
                "pending": stats['today_pending_count'] or 0
            }
        }