from django.db import models
import datetime
from django.utils import timezone
from django.db.models import Q
from .managers import AppointmentQuerySet

class Shop(models.Model):
    """多租戶架構核心：店家模型"""
    name = models.CharField(max_length=100, verbose_name="店家名稱")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Customer(models.Model):
    """會員模型：以手機或 LINE UID 為唯一識別"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='customers')
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="手機號碼")
    line_uid = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name="LINE UID")
    name = models.CharField(max_length=50, verbose_name="姓名")
    email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"

class Provider(models.Model):
    """服務人員 (美業師) 模型"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='providers')
    name = models.CharField(max_length=50, verbose_name="人員名稱")
    is_manager = models.BooleanField(default=False, verbose_name="是否為店長")
    
    def __str__(self):
        return self.name
    
    def get_available_slots(self, target_date: datetime.date, service_item: 'ServiceItem') -> list:
        """
        計算該人員在特定日期的所有可用時段。
        """
        # 1. 取得人員當天的排班時間 
        # (這裡先寫死 10:00 - 20:00，未來你可以串接你規劃的「人員自定義可預約時段」資料表)
        work_start_time = datetime.time(10, 0)
        work_end_time = datetime.time(20, 0)

        # 處理時區問題 (Django 專案必備，避免 UTC 與台灣時間的落差)
        current_tz = timezone.get_current_timezone()
        work_start_dt = timezone.make_aware(
            datetime.datetime.combine(target_date, work_start_time), 
            current_tz
        )
        work_end_dt = timezone.make_aware(
            datetime.datetime.combine(target_date, work_end_time), 
            current_tz
        )

        # 2. ORM 精準打擊：只撈取「當天」且「佔用中」的訂單
        # 佔用中定義 = 狀態為 PENDING (待確認) 或 CONFIRMED (已確認)
        occupied_appointments = self.appointments.filter(
            start_time__gte=work_start_dt,
            start_time__lt=work_end_dt
        ).filter(
            Q(status='PENDING') | Q(status='CONFIRMED')
        ).order_by('start_time')

        # 3. 準備時段切分參數
        service_duration = datetime.timedelta(minutes=service_item.duration_minutes)
        # 設定每個可選時段的間隔 (例如：每 30 分鐘開放一個預約點，像是 10:00, 10:30, 11:00)
        slot_interval = datetime.timedelta(minutes=30) 
        
        available_slots = []
        current_time = work_start_dt

        # 4. 時段掃描迴圈 (Time Slot Scanning)
        while current_time + service_duration <= work_end_dt:
            slot_start = current_time
            slot_end = current_time + service_duration
            is_overlapping = False

            # 檢查這個假定的時段，是否與任何現存訂單碰撞
            for appt in occupied_appointments:
                # 【黃金碰撞公式】：(A開始 < B結束) 且 (A結束 > B開始)
                # 只要滿足此條件，就代表兩個時間區間有重疊
                if slot_start < appt.end_time and slot_end > appt.start_time:
                    is_overlapping = True
                    break # 只要撞到一個，這個時段就報廢，不用繼續比對後面的訂單

            # 如果沒有碰撞，就加入可用清單
            if not is_overlapping:
                available_slots.append({
                    "start_time": slot_start.isoformat(),
                    "end_time": slot_end.isoformat()
                })

            # 推進到下一個預約點 (例如 10:00 檢查完，換檢查 10:30)
            current_time += slot_interval

        return available_slots

class ServiceItem(models.Model):
    """服務項目模型"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100, verbose_name="項目名稱")
    description = models.TextField(blank=True, verbose_name="描述")
    duration_minutes = models.PositiveIntegerField(verbose_name="實作時間(分鐘)")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="價格")
    # 關鍵：多對多關聯，定義哪些人員可以提供這項服務
    providers = models.ManyToManyField(Provider, related_name='provided_services')

    def __str__(self):
        return self.name

class Appointment(models.Model):
    """預約訂單模型 (嚴格狀態機)"""
    STATUS_CHOICES = [
        ('PENDING', '待確認'),
        ('CONFIRMED', '已確認'),
        ('CANCELLED', '已取消'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='appointments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='appointments')
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(ServiceItem, on_delete=models.CASCADE)
    
    start_time = models.DateTimeField(verbose_name="開始時間")
    end_time = models.DateTimeField(verbose_name="結束時間")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="預約狀態")
    memo = models.TextField(blank=True, verbose_name="客戶備註")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentQuerySet.as_manager()
    
    @property
    def is_cancellable(self):
        """Fat Model 實作：判斷目前是否允許客人自行取消 (例如：提前 24 小時)"""
        time_difference = self.start_time - timezone.now()
        return time_difference.total_seconds() > 86400  # 24小時 = 86400秒

    def __str__(self):
        return f"{self.customer.name} - {self.service.name} ({self.start_time.strftime('%m/%d %H:%M')})"

class ServiceRecord(models.Model):
    """施作紀錄與材料追蹤"""
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='record')
    image_url = models.URLField(blank=True, null=True, verbose_name="成品圖網址") # 未來可串接 AWS S3 或直接存 URL
    materials_note = models.TextField(blank=True, verbose_name="材料與色號紀錄")
    created_at = models.DateTimeField(auto_now_add=True)