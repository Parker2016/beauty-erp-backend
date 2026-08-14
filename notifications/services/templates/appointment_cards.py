# notifications/services/templates/appointment_cards.py
from django.utils import timezone


def build_new_appointment_group_card(
    appointment, admin_url="https://your-admin.com"
):
    """根據實際 Model 結構生成 LINE Flex Message 預約通知卡片"""
    # 1. 取得顧客資訊
    customer = getattr(appointment, "customer", None)
    customer_name = customer.name if customer else "未留姓名"
    customer_phone = customer.phone if customer else "未提供"

    # 2. 取得美甲師與分店資訊
    provider = getattr(appointment, "provider", None)
    provider_name = provider.name if provider else "不指定/未分配"
    shop_id = getattr(appointment, "shop_id", 1)

    # 3. 取得預約主項目與加購項目
    main_services = (
        list(appointment.services.all())
        if hasattr(appointment, "services")
        else []
    )
    addons = (
        list(appointment.addons.all()) if hasattr(appointment, "addons") else []
    )

    service_names_list = [s.name for s in main_services]
    if addons:
        service_names_list.extend([f"加購:{a.name}" for a in addons])

    services_display = (
        " + ".join(service_names_list) if service_names_list else "未指定項目"
    )

    # 4. 計算預估金額 (若已有 final_price 則優先顯示)
    if appointment.final_price:
        price_display = f"${appointment.final_price:,}"
    else:
        total_estimate = sum(s.price for s in main_services) + sum(
            a.price for a in addons
        )
        price_display = (
            f"${total_estimate:,} (預估)" if total_estimate > 0 else "現場報價"
        )

    # 5. 處理時間 (轉換至台灣時區並格式化)
    if appointment.start_time:
        local_start = timezone.localtime(appointment.start_time)
        time_str = local_start.strftime("%Y/%m/%d (%a) %H:%M")
    else:
        time_str = "時間未定"

    # 6. 客戶備註
    memo_display = appointment.memo if appointment.memo else "無"

    # 後台審核連結 (直接帶入該分店的 admin 網址)
    target_admin_url = f"{admin_url.rstrip('/')}/admin/{shop_id}"

    # 7. 組裝 Flex Message Bubble JSON
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🔔 收到新預約單・待確認",
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "md",
                }
            ],
            "backgroundColor": "#D88A8A",
            "paddingAll": "15px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"預約編號 #{appointment.id}",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#333333",
                },
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        # 顧客姓名
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "預約顧客",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": customer_name,
                                    "weight": "bold",
                                    "color": "#333333",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        # 聯絡電話
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "聯絡電話",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": customer_phone,
                                    "color": "#333333",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        # 預約時間
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "預約時段",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": time_str,
                                    "weight": "bold",
                                    "color": "#D88A8A",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        # 指派美甲師
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "服務人員",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": provider_name,
                                    "color": "#333333",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        # 服務項目
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "施作項目",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": services_display,
                                    "color": "#333333",
                                    "size": "sm",
                                    "flex": 5,
                                    "wrap": True,
                                },
                            ],
                        },
                        # 預估金額
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "預估金額",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": price_display,
                                    "weight": "bold",
                                    "color": "#27ae60",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        # 備註
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "客戶備註",
                                    "color": "#888888",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": memo_display,
                                    "color": "#666666",
                                    "size": "sm",
                                    "flex": 5,
                                    "wrap": True,
                                },
                            ],
                        },
                    ],
                },
            ],
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
                        "uri": target_admin_url,
                    },
                    "style": "primary",
                    "color": "#D88A8A",
                    "height": "sm",
                }
            ],
            "paddingAll": "15px",
        },
    }