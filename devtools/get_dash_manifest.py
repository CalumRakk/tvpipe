import requests

url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/VIDEOURL/LIVE/43/10"
headers = {
    "Restful": "yes",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}

response = requests.get(url, headers=headers)

print(response.status_code)
print(response.text)  # o response.json() si el contenido es JSON
