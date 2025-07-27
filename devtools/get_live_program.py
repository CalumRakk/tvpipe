import requests

url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/SEARCH/PROGRAM"
params = {"filter_channelIds": "43", "filter_airingTime": "now"}
headers = {
    "Restful": "yes",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}

response = requests.get(url, params=params, headers=headers)

print(response.status_code)
print(response.text)  # o response.json() si esperas una respuesta JSON
