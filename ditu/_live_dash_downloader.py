import os
import time
import xml.etree.ElementTree as ET

import requests

# ============================
# CONFIGURACIÓN
# ============================

MPD_URL = "https://d1kkcfjl98zuzm.cloudfront.net/v1/dash/f4489bb8f722c0b62ee6ef7424a5804a17ae814a/El-Desafio/out/v1/ab964e48d2c041579637cfe179ff2359/index.mpd"

PARAMS = {
    "ads.deviceType": "mobile",
    "ads.rdid": "05166e3c-d22e-4386-9d0a-6aadf1d5c62f",
    "ads.is_lat": "0",
    "ads.idtype": "adid",
    "ads.vpa": "auto",
}

HEADERS = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}

OUTPUT_DIR_VIDEO = "output_dash/video"
OUTPUT_DIR_AUDIO = "output_dash/audio"

REPRESENTATION_ID_VIDEO = "3"
REPRESENTATION_ID_AUDIO = "4"

# ============================
# FUNCIONES
# ============================


def download_mpd():
    response = requests.get(MPD_URL, headers=HEADERS, params=PARAMS)
    response.raise_for_status()
    return response.text


def parse_mpd(xml_text, representation_id):
    ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
    root = ET.fromstring(xml_text)

    base_url = root.find("mpd:BaseURL", ns).text

    for aset in root.findall(".//mpd:AdaptationSet", ns):
        for rep in aset.findall("mpd:Representation", ns):
            if rep.attrib["id"] == representation_id:
                template = rep.find("mpd:SegmentTemplate", ns)
                timeline = template.find("mpd:SegmentTimeline", ns)

                init_url = template.attrib["initialization"]
                media_pattern = template.attrib["media"]
                start_number = int(template.attrib["startNumber"])

                segments = []
                for s in timeline.findall("mpd:S", ns):
                    repeat = int(s.attrib.get("r", 0))
                    segments += [s] * (repeat + 1)

                return {
                    "base_url": base_url,
                    "init_url": base_url + init_url,
                    "media_pattern": base_url + media_pattern,
                    "start_number": start_number,
                    "segments": segments,
                }

    raise Exception(f"No se encontró Representation ID {representation_id}")


def download_file(url, output_path):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(r.content)
    print(f"✅ Descargado: {output_path}")


# ============================
# LOOP PRINCIPAL
# ============================

os.makedirs(OUTPUT_DIR_VIDEO, exist_ok=True)
os.makedirs(OUTPUT_DIR_AUDIO, exist_ok=True)

downloaded_numbers_video = set()
downloaded_numbers_audio = set()

print("📥 Descargando MPD inicial...")
mpd_text = download_mpd()

# Descarga init video
mpd_info_video = parse_mpd(mpd_text, REPRESENTATION_ID_VIDEO)
download_file(mpd_info_video["init_url"], os.path.join(OUTPUT_DIR_VIDEO, "init.mp4"))

# Descarga init audio
mpd_info_audio = parse_mpd(mpd_text, REPRESENTATION_ID_AUDIO)
download_file(mpd_info_audio["init_url"], os.path.join(OUTPUT_DIR_AUDIO, "init.mp4"))

while True:
    try:
        print("📥 Actualizando MPD...")
        mpd_text = download_mpd()

        # Video
        mpd_info_video = parse_mpd(mpd_text, REPRESENTATION_ID_VIDEO)
        for idx, _ in enumerate(mpd_info_video["segments"]):
            seg_num = mpd_info_video["start_number"] + idx
            if seg_num not in downloaded_numbers_video:
                seg_url = mpd_info_video["media_pattern"].replace(
                    "$Number$", str(seg_num)
                )
                seg_path = os.path.join(OUTPUT_DIR_VIDEO, f"segment_{seg_num}.mp4")
                download_file(seg_url, seg_path)
                downloaded_numbers_video.add(seg_num)

        # Audio
        mpd_info_audio = parse_mpd(mpd_text, REPRESENTATION_ID_AUDIO)
        for idx, _ in enumerate(mpd_info_audio["segments"]):
            seg_num = mpd_info_audio["start_number"] + idx
            if seg_num not in downloaded_numbers_audio:
                seg_url = mpd_info_audio["media_pattern"].replace(
                    "$Number$", str(seg_num)
                )
                seg_path = os.path.join(OUTPUT_DIR_AUDIO, f"segment_{seg_num}.mp4")
                download_file(seg_url, seg_path)
                downloaded_numbers_audio.add(seg_num)

        print("🕒 Esperando próximo ciclo...")
        time.sleep(5)  # Igual a minimumUpdatePeriod

    except KeyboardInterrupt:
        print("⏹️ Cancelado por el usuario.")
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(5)
