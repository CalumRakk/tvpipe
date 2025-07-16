import json

import requests

# URL de destino
url = "https://business-api.tiktok.com/open_api/v1.2/app/monitor/"

# Encabezados HTTP
headers = {
    "Connection": "keep-alive",
    "User-Agent": "tiktok-business-android-sdk/1.3.3/v1.2",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Host": "business-api.tiktok.com",
}

payload = {
    "tiktok_app_id": 7471660800021725192,
    "event_source": "APP_EVENTS_SDK",
    "batch": [
        {
            "app": {
                "id": "com.caracol.streaming",
                "name": "ditu",
                "namespace": "com.caracol.streaming",
                "version": "1.17.0",
                "build": "343",
                "tiktok_app_id": "7471660800021725192",
                "app_namespace": "com.caracol.streaming",
            },
            "library": {
                "name": "tiktok/tiktok-business-android-sdk",
                "version": "1.3.3",
            },
            "device": {
                "platform": "Android",
                "gaid": "05166e3c-d22e-4386-9d0a-6aadf1d5c62f",
                "version": "31",
                "id": "acf44ac3-843b-4911-9031-085ff0eb9de1",
                "user_agent": "Mozilla/5.0 (Linux; Android 12; M2003J15SC Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.67 Mobile Safari/537.36",
                "ip": "192.168.1.3",
                "network": "WIFI",
                "session": "d2b219e8-8bb0-449d-a674-7c05e6f79709",
                "locale": "es-US",
                "ts": 1752433826927,
            },
            "monitor": {
                "type": "metric",
                "name": "init_start",
                "meta": {"ts": 1752646637321},
            },
        },
    ],
}

response = requests.post(url, headers=headers, json=payload)
print("Status Code:", response.status_code)
print("Response Body:", response.text)
