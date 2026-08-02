# booking/models.py (或你的 Manager 檔案)
import calendar
from datetime import datetime, time, timedelta
from django.db import models
from django.db.models import Sum, Count, Q
from django.utils import timezone

class AppointmentQuerySet(models.QuerySet):
    
    def for_shop_calendar(self, shop_id, start_date_str, end_date_str, provider_id=None):
        """核心邏輯：過濾行事曆時間區間 (支援依美甲師過濾)"""
        start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        aware_start = timezone.make_aware(datetime.combine(start_d, time.min))
        aware_end = timezone.make_aware(datetime.combine(end_d, time.max))
        
        queryset = self.filter(
            shop_id=shop_id,
            start_time__gte=aware_start,
            start_time__lte=aware_end
        )

        # 💡 新增：若有指定美甲師且不是全部，則進行篩選
        if provider_id and str(provider_id) != 'all':
            queryset = queryset.filter(provider_id=provider_id)

        return queryset.select_related(
            'customer', 'provider'
        ).prefetch_related(
            'services', 'addons'
        ).order_by('start_time')

    def get_dashboard_stats(self, shop_id, provider_id=None):
        """核心邏輯：計算營收與看板指標 (支援依美甲師過濾)"""
        local_now = timezone.localtime(timezone.now())
        
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = local_now.replace(hour=23, minute=59, second=59, microsecond=999999)

        week_start = today_start - timedelta(days=today_start.weekday())
        week_end = (week_start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)

        month_start = today_start.replace(day=1)
        _, last_day = calendar.monthrange(month_start.year, month_start.month)
        month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

        revenue_states = ['PENDING', 'CONFIRMED', 'COMPLETED']

        # 基礎 queryset 綁定 shop_id
        base_qs = self.filter(shop_id=shop_id)

        # 💡 新增：若有指定美甲師且不是全部，則縮小統計範圍至該美甲師
        if provider_id and str(provider_id) != 'all':
            base_qs = base_qs.filter(provider_id=provider_id)

        stats = base_qs.aggregate(
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