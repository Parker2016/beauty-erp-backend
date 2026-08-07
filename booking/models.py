from django.db import models
import datetime
from django.utils import timezone
from django.db.models import Q
from .managers import AppointmentQuerySet
from django.core.exceptions import ObjectDoesNotExist

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
    
    def get_available_slots(self, target_date: datetime.date, service_items, addon_items: list = None) -> list:
        current_tz = timezone.get_current_timezone()

        try:
            shift = self.shifts.get(date=target_date)
        except ObjectDoesNotExist:
            return []

        if shift.is_off or not shift.start_time or not shift.end_time:
            return []

        work_start_dt = timezone.make_aware(
            datetime.datetime.combine(target_date, shift.start_time), 
            current_tz
        )
        work_end_dt = timezone.make_aware(
            datetime.datetime.combine(target_date, shift.end_time), 
            current_tz
        )

        occupied_appointments = self.appointments.filter(
            start_time__gte=work_start_dt,
            start_time__lt=work_end_dt
        ).filter(
            Q(status='PENDING') | Q(status='CONFIRMED')
        ).order_by('start_time')

        break_intervals = []
        if shift.break_times:
            for b in shift.break_times:
                b_start_time = datetime.datetime.strptime(b.get('start'), '%H:%M').time()
                b_end_time = datetime.datetime.strptime(b.get('end'), '%H:%M').time()
                
                b_start_dt = timezone.make_aware(datetime.datetime.combine(target_date, b_start_time), current_tz)
                b_end_dt = timezone.make_aware(datetime.datetime.combine(target_date, b_end_time), current_tz)
                
                break_intervals.append({'start_time': b_start_dt, 'end_time': b_end_dt})

        if isinstance(service_items, (list, tuple)):
            main_duration = sum(s.duration_minutes for s in service_items)
        else:
            main_duration = getattr(service_items, 'duration_minutes', 0)

        addon_duration = sum(addon.duration_minutes for addon in addon_items) if addon_items else 0
        total_duration_minutes = main_duration + addon_duration

        service_duration = datetime.timedelta(minutes=total_duration_minutes)
        slot_interval = datetime.timedelta(minutes=30) 
        
        available_slots = []
        current_time = work_start_dt

        while current_time + service_duration <= work_end_dt:
            slot_start = current_time
            slot_end = current_time + service_duration
            is_overlapping = False

            for appt in occupied_appointments:
                if slot_start < appt.end_time and slot_end > appt.start_time:
                    is_overlapping = True
                    break 

            if not is_overlapping:
                for break_item in break_intervals:
                    if slot_start < break_item['end_time'] and slot_end > break_item['start_time']:
                        is_overlapping = True
                        break

            if not is_overlapping:
                available_slots.append({
                    "start_time": slot_start.isoformat(),
                    "end_time": slot_end.isoformat()
                })

            current_time += slot_interval

        return available_slots

class ProviderShift(models.Model):
    """美甲師每日班表模型"""
    provider = models.ForeignKey(
        'Provider', 
        on_delete=models.CASCADE, 
        related_name='shifts',
        verbose_name="美甲師"
    )
    date = models.DateField(verbose_name="排班日期")
    start_time = models.TimeField(null=True, blank=True, verbose_name="上班時間")
    end_time = models.TimeField(null=True, blank=True, verbose_name="下班時間")
    is_off = models.BooleanField(default=False, verbose_name="是否公休")
    break_times = models.JSONField(default=list, blank=True, verbose_name="當日休息時段")

    class Meta:
        verbose_name = "美甲師班表"
        verbose_name_plural = "美甲師班表"
        constraints = [
            models.UniqueConstraint(fields=['provider', 'date'], name='unique_provider_date_shift')
        ]
        indexes = [
            models.Index(fields=['provider', 'date']),
        ]

    def __str__(self):
        status = "公休" if self.is_off else f"{self.start_time} - {self.end_time}"
        return f"[{self.date}] {self.provider.name} : {status}"
    
class ServiceItem(models.Model):
    """服務項目模型"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100, verbose_name="項目名稱")
    description = models.TextField(blank=True, verbose_name="描述")
    duration_minutes = models.PositiveIntegerField(verbose_name="實作時間(分鐘)")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="價格")
    providers = models.ManyToManyField(Provider, related_name='provided_services')

    is_addon = models.BooleanField(default=False, verbose_name="是否為加購項")
    
    PRICE_TYPE_CHOICES = [
        ('FIXED', '固定定價'),
        ('STARTING', '最低起價'),
        ('QUOTE', '現場溝通報價'),
    ]
    price_type = models.CharField(max_length=10, choices=PRICE_TYPE_CHOICES, default='FIXED')
    
    CATEGORY_CHOICES = [
        ('HAND', '手部美甲'),
        ('FOOT', '足部美甲'),
        ('PURE_REMOVAL', '純保養/純卸甲'),
        ('EAR', '采耳'),
        ('ADDON', '加購項目'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='HAND')

    def __str__(self):
        return self.name

class Appointment(models.Model):
    """預約訂單模型"""
    STATUS_CHOICES = [
        ('PENDING', '待確認'),
        ('CONFIRMED', '已確認'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='appointments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='appointments')
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='appointments')
    services = models.ManyToManyField('ServiceItem', related_name='appointments', verbose_name="預約服務項目")
    addons = models.ManyToManyField(ServiceItem, blank=True, related_name='addon_appointments')

    start_time = models.DateTimeField(verbose_name="開始時間")
    end_time = models.DateTimeField(verbose_name="結束時間")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="預約狀態")
    
    final_price = models.IntegerField(null=True, blank=True, verbose_name="實際收費")
    memo = models.TextField(blank=True, verbose_name="客戶備註")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentQuerySet.as_manager()
    
    @property
    def is_cancellable(self):
        if not self.start_time:
            return False
        time_difference = self.start_time - timezone.now()
        return time_difference.total_seconds() > 86400

    def __str__(self):
        if self.pk and self.services.exists():
            service_names = " + ".join([s.name for s in self.services.all()])
        else:
            service_names = "無指定項目"

        customer_name = self.customer.name if hasattr(self, 'customer') and self.customer else "未知顧客"
        time_str = self.start_time.strftime('%m/%d %H:%M') if self.start_time else ""

        return f"{customer_name} - {service_names} ({time_str})"

class ServiceRecord(models.Model):
    """施作紀錄與材料追蹤"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='service_records', verbose_name="店家")
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='record')
    image_url = models.URLField(blank=True, null=True, verbose_name="成品圖網址")
    materials_note = models.TextField(blank=True, verbose_name="材料與色號紀錄")
    created_at = models.DateTimeField(auto_now_add=True)

class DesignPriceCategory(models.TextChoices):
    BASE = 'BASE', '款式底價'
    ADDON = 'ADDON', '加價項目'
    STYLE = 'STYLE', '進階造型'
    REMOVAL = 'REMOVAL', '卸甲服務'

class DesignPriceItem(models.Model):
    """設計款價目表模板"""
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, related_name='design_price_items')
    category = models.CharField(max_length=20, choices=DesignPriceCategory.choices, verbose_name="項目分類")
    name = models.CharField(max_length=100, verbose_name="項目名稱")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="預設單價")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="顯示排序")
    is_active = models.BooleanField(default=True, verbose_name="是否上架")

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = "設計款價目項目"

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name} - ${self.price}"

class AppointmentDesignQuote(models.Model):
    """預約單的設計款結帳總表"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='design_quotes', verbose_name="店家")
    appointment = models.OneToOneField(
        'Appointment', 
        on_delete=models.CASCADE, 
        related_name='design_quote',
        verbose_name="關聯預約單"
    )
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="預收定金")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="優惠折扣")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="項目小計")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="應付尾款")
    formatted_receipt = models.TextField(blank=True, verbose_name="格式化明細文字快照")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 自動從關聯的 appointment 帶入 shop，維持資料一致性
        if self.appointment and not self.shop_id:
            self.shop = self.appointment.shop
            
        super().save(*args, **kwargs)
        
        if self.appointment and self.appointment.final_price != self.total_amount:
            self.appointment.final_price = self.total_amount
            self.appointment.save(update_fields=['final_price'])

class AppointmentDesignItem(models.Model):
    """結帳單項目明細快照"""
    quote = models.ForeignKey(AppointmentDesignQuote, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=20, choices=DesignPriceCategory.choices, verbose_name="分類")
    item_name = models.CharField(max_length=100, verbose_name="項目名稱快照")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="單價快照")
    quantity = models.PositiveIntegerField(default=1, verbose_name="數量")
    is_custom = models.BooleanField(default=False, verbose_name="是否為現場臨時新增項目")

    @property
    def item_total(self):
        return self.unit_price * self.quantity