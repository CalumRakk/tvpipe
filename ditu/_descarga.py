import os
import xml.etree.ElementTree as ET

import requests

# ================================
# CONFIGURACIÓN
# ================================

MPD_FILE = "data.txt"
OUTPUT_DIR = "output_dash"
ADAPTATION_SET_ID = "1"  # video 720p es id=1

# ================================
# PARSEAR MPD
# ================================

tree = ET.parse(MPD_FILE)
root = tree.getroot()
ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

base_url = root.find("mpd:BaseURL", ns).text

# Encontrar AdaptationSet y Representation deseados
adaptation_sets = root.findall(".//mpd:AdaptationSet", ns)

segment_info = {}

for aset in adaptation_sets:
    for rep in aset.findall("mpd:Representation", ns):
        rep_id = rep.attrib["id"]
        if rep_id == ADAPTATION_SET_ID:
            template = rep.find("mpd:SegmentTemplate", ns)
            timeline = template.find("mpd:SegmentTimeline", ns)

            init_url = template.attrib["initialization"]
            media_pattern = template.attrib["media"]
            start_number = int(template.attrib["startNumber"])

            segments = []
            for s in timeline.findall("mpd:S", ns):
                repeat = int(s.attrib.get("r", 0))
                segments += [s] * (repeat + 1)

            segment_info = {
                "init_url": base_url + init_url,
                "media_pattern": base_url + media_pattern,
                "start_number": start_number,
                "segment_count": len(segments),
            }
            break

print(f"Base URL: {base_url}")
print(f"Descargando init: {segment_info['init_url']}")
print(f"Total segmentos: {segment_info['segment_count']}")

# ================================
# DESCARGAR SEGMENTOS
# ================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

r = requests.get(segment_info["init_url"])
with open(os.path.join(OUTPUT_DIR, "init.mp4"), "wb") as f:
    f.write(r.content)

number = segment_info["start_number"]
for i in range(segment_info["segment_count"]):
    segment_url = segment_info["media_pattern"].replace("$Number$", str(number))
    print(f"Descargando segmento #{number} - {segment_url}")

    r = requests.get(segment_url)
    with open(os.path.join(OUTPUT_DIR, f"segment_{number}.mp4"), "wb") as f:
        f.write(r.content)

    number += 1

print("✅ Descarga completa")
