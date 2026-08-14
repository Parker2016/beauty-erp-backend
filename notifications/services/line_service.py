# notifications/services/line_service.py
import requests
import logging
from django.conf import settings
from .templates.appointment_cards import build_new_appointment_group_card

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_line_push_message(to_id: str, messages: list) -> bool:
    """
    底層發送 LINE Push Message (純 requests，零 SDK 依賴)
    """
    token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', '')
    if not token or not to_id:
        logger.error("LINE 推播失敗：缺少 ACCESS_TOKEN 或 目標 ID")
        return False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "to": to_id,
        "messages": messages
    }

    try:
        response = requests.post(LINE_PUSH_URL, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            logger.info(f"LINE 推播成功發送至: {to_id}")
            return True
        else:
            logger.error(f"LINE 推播失敗 (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"LINE 推播連線異常: {str(e)}")
        return False


def notify_new_appointment_to_group(appointment) -> bool:
    """
    取得新預約卡片樣式並推播至工作群組
    """
    group_id = getattr(settings, 'LINE_WORK_GROUP_ID', '')
    if not group_id:
        logger.warning("未設定 LINE_WORK_GROUP_ID，略過群組推播。")
        return False

    admin_url = getattr(settings, 'ADMIN_FRONTEND_URL', 'https://your-admin.com')
    
    # 💡 呼叫 template 模組生成卡片 JSON
    flex_card = build_new_appointment_group_card(appointment, admin_url=admin_url)
    customer_name = getattr(appointment, 'customer_name', '顧客')

    messages = [
        {
            "type": "flex",
            "altText": f"🔔 收到【{customer_name}】的新預約單待確認！",
            "contents": flex_card
        }
    ]

    return send_line_push_message(group_id, messages)