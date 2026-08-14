# notifications/views.py
import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

@csrf_exempt
def line_webhook(request):
    """
    寬容模式 Webhook：
    1. 支援所有 Method (GET, POST, OPTIONS, HEAD)，保證 Verify 必過
    2. 印出收到的 Method 與 Body 供排查
    """
    # 💡 印出請求細節到 Render Log
    print(f"\n[LINE Webhook] 收到請求 Method: {request.method}", flush=True)

    # 如果是 GET / HEAD (瀏覽器測試或轉址)
    if request.method != 'POST':
        return HttpResponse("LINE Webhook OK", status=200)

    body = request.body.decode('utf-8')
    print(f"[LINE Webhook] 收到 Body: {body}", flush=True)

    # 解析事件並抓取 Group ID / User ID
    try:
        if body:
            payload = json.loads(body)
            events = payload.get('events', [])
            for event in events:
                source = event.get('source', {})
                print(f"👉 事件類型: {event.get('type')}, 來源類型: {source.get('type')}", flush=True)
                
                if 'groupId' in source:
                    print(f"🎉🎉🎉 抓到 Group ID: {source['groupId']}", flush=True)
                elif 'userId' in source:
                    print(f"👤 抓到 User ID: {source['userId']}", flush=True)
    except Exception as e:
        print(f"解析 JSON 失敗: {e}", flush=True)

    # 永遠回傳 200 給 LINE
    return HttpResponse("OK", status=200)