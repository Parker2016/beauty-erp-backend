from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        profile = getattr(user, 'profile', None)
        if profile:
            token['shop_id'] = profile.shop.id
            token['role'] = profile.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        profile = getattr(self.user, 'profile', None)
        if not profile:
            raise serializers.ValidationError({"detail": "該帳號尚未綁定店家與角色權限，請聯繫系統管理員。"})

        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'role': profile.role,
            'shop_id': profile.shop.id,
            'shop_name': profile.shop.name,
            'provider_id': profile.provider.id if profile.provider else None
        }
        return data