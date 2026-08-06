from django.db import models
from django.contrib.auth.models import User
from booking.models import Shop, Provider  # 從 booking 引用 Shop 與 Provider

class UserRole(models.TextChoices):
    MANAGER = 'MANAGER', '店長'
    STAFF = 'STAFF', '美甲師'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="使用者帳號")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='user_profiles', verbose_name="所屬店家")
    role = models.CharField(max_length=10, choices=UserRole.choices, default=UserRole.STAFF, verbose_name="角色權限")
    provider = models.OneToOneField(
        Provider, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='user_profile',
        verbose_name="關聯的美甲師實體"
    )

    class Meta:
        verbose_name = "工作人員權限檔"
        verbose_name_plural = "工作人員權限檔"

    def __str__(self):
        return f"[{self.shop.name}] {self.user.username} ({self.get_role_display()})"