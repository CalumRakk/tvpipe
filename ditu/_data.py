from pathlib import Path

import requests

url = "https://d1kkcfjl98zuzm.cloudfront.net/v1/dash/f4489bb8f722c0b62ee6ef7424a5804a17ae814a/El-Desafio/out/v1/ab964e48d2c041579637cfe179ff2359/index.mpd"

# Parámetros de la query string
params = {
    "ads.deviceType": "mobile",
    "ads.rdid": "05166e3c-d22e-4386-9d0a-6aadf1d5c62f",
    "ads.is_lat": "0",
    "ads.idtype": "adid",
    "ads.vpa": "auto",
}

# Encabezados
headers = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}

response = requests.get(url, headers=headers, params=params)

Path("data.txt").write_text(response.text)
print("MPD file downloaded and saved as data.txt")
