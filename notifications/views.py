import json
import hmac
import hashlib
import base64
import logging
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

logger = logging.getLogger(__name__)

# 請確保 settings.py 或 .env 有設定 LINE_CHANNEL_SECRET
LINE_CHANNEL_SECRET = getattr(settings, 'LINE_CHANNEL_SECRET', '你的_LINE_CHANNEL_SECRET')

@csrf_exempt
def line_webhook(request):
    """接收 LINE Webhook 事件"""
    # 💡 允許 GET 請求（方便瀏覽器直接訪問測試）
    if request.method == 'GET':
        return HttpResponse('LINE Webhook Endpoint is Running!', status=200)

    if request.method != 'POST':
        return HttpResponse('Method Not Allowed', status=405)

    signature = request.META.get('HTTP_X_LINE_SIGNATURE', '')
    body = request.body.decode('utf-8')
    channel_secret = getattr(settings, 'LINE_CHANNEL_SECRET', '')

    # 1. 驗證 LINE 簽章 (如果有設定 Secret 才驗證)
    if channel_secret and signature:
        hash_value = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        computed_signature = base64.b64encode(hash_value).decode('utf-8')

        if signature != computed_signature:
            logger.warning('LINE Webhook 簽章驗證失敗！')
            return HttpResponseForbidden('Invalid Signature')

    # 2. 解析事件（LINE Verify 點擊時 events 會是空陣列 []）
    try:
        if body:
            payload = json.loads(body)
            events = payload.get('events', [])

            for event in events:
                source = event.get('source', {})
                event_type = event.get('type')
                source_type = source.get('type')

                # 當事件來自群組時，印出 groupId
                if source_type == 'group':
                    group_id = source.get('groupId')
                    print('\n' + '=' * 60)
                    print(f'🎉 成功偵測到 LINE 群組事件 (Type: {event_type})')
                    print(f'👉 Group ID: {group_id}')
                    print('請將此 ID 複製並填入 .env 的 LINE_WORK_GROUP_ID')
                    print('=' * 60 + '\n')

    except Exception as e:
        logger.error(f'解析 LINE Webhook 異常: {str(e)}')

    # 3. 永遠回傳 200 給 LINE
    return HttpResponse('OK', status=200)