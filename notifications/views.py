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
    if request.method != 'POST':
        return HttpResponse("Method Not Allowed", status=405)

    # 1. 驗證 LINE 簽章 (Signature)
    signature = request.META.get('HTTP_X_LINE_SIGNATURE', '')
    body = request.body.decode('utf-8')

    # 使用 Python 內建 hmac 驗證來源是否合法
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    computed_signature = base64.b64encode(hash_value).decode('utf-8')

    if signature != computed_signature:
        logger.warning("LINE Webhook 簽章驗證失敗！")
        return HttpResponseForbidden("Invalid Signature")

    # 2. 解析事件內容並擷取 Group ID
    try:
        data = json.loads(body)
        events = data.get('events', [])

        for event in events:
            source = event.get('source', {})
            source_type = source.get('type')

            # 💡 當事件來自群組 (group) 時，擷取 groupId
            if source_type == 'group':
                group_id = source.get('groupId')
                print("\n" + "=" * 50)
                print(f"🎉🎉🎉 成功抓到 LINE 群組 Group ID: {group_id}")
                print("=" * 50 + "\n")

    except Exception as e:
        logger.error(f"解析 LINE Webhook 失敗: {e}")

    # 3. 必須回傳 HTTP 200 給 LINE
    return HttpResponse("OK", status=200)