# notifications/services/templates/appointment_cards.py
from datetime import datetime

def format_datetime(dt) -> str:
    """輔助函數：安全格式化時間"""
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d (%a) %H:%M')
    return str(dt) if dt else '待確認'


def build_new_appointment_group_card(appointment, admin_url: str) -> dict:
    """
    組裝【發送至工作群組】的新預約待確認 Flex Message 卡片
    """
    customer_name = getattr(appointment, 'customer_name', '顧客')
    customer_phone = getattr(appointment, 'customer_phone', '未提供')
    provider_name = getattr(appointment.provider, 'name', '不指定') if appointment.provider else '不指定'
    service_name = getattr(appointment.service, 'name', '一般項目') if hasattr(appointment, 'service') and appointment.service else '一般項目'
    price = getattr(appointment, 'total_price', getattr(appointment.service, 'price', 0))
    start_time_str = format_datetime(getattr(appointment, 'start_time', None))
    note = getattr(appointment, 'notes', '') or '無特殊備註'

    # 如果有加購項目 (例如 items 或 addons)
    addons = getattr(appointment, 'addons', [])
    addon_names = "、".join([getattr(a, 'name', str(a)) for a in addons]) if addons else ""

    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🔔 收到新預約單・待確認",
                    "weight": "bold",
                    "size": "md",
                    "color": "#8C7654"
                }
            ],
            "backgroundColor": "#FBF9F5",
            "paddingBottom": "12px",
            "paddingTop": "14px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "sm",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "顧客姓名", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": str(customer_name), "wrap": True, "color": "#111111", "size": "sm", "flex": 7, "weight": "bold"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "聯絡電話", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": str(customer_phone), "wrap": True, "color": "#333333", "size": "sm", "flex": 7}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "預約時段", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": start_time_str, "wrap": True, "color": "#111111", "size": "sm", "flex": 7, "weight": "bold"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "主要項目", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": str(service_name), "wrap": True, "color": "#333333", "size": "sm", "flex": 7}
                            ]
                        },
                        *(
                            [
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {"type": "text", "text": "加購項目", "color": "#888888", "size": "sm", "flex": 3},
                                        {"type": "text", "text": addon_names, "wrap": True, "color": "#333333", "size": "sm", "flex": 7}
                                    ]
                                }
                            ] if addon_names else []
                        ),
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "指定人員", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": str(provider_name), "wrap": True, "color": "#333333", "size": "sm", "flex": 7}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "預估金額", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": f"NT$ {price}", "wrap": True, "color": "#8C7654", "size": "sm", "flex": 7, "weight": "bold"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "顧客備註", "color": "#888888", "size": "sm", "flex": 3},
                                {"type": "text", "text": str(note), "wrap": True, "color": "#666666", "size": "xs", "flex": 7}
                            ]
                        }
                    ]
                }
            ],
            "paddingBottom": "10px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "⚡ 開啟後台審核預約",
                        "uri": admin_url
                    },
                    "style": "primary",
                    "color": "#222222",
                    "height": "sm"
                }
            ],
            "paddingTop": "4px"
        }
    }