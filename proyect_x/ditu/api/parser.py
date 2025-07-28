import xml.etree.ElementTree as ET
from typing import Dict, List


class MPDInfo:
    """
    Representa la información relevante de una representación (audio/video) en un manifiesto DASH (MPD).
    """

    def __init__(
        self,
        base_url: str,
        init_url: str,
        media_pattern: str,
        start_number: int,
        segments: List,
        mimetype: str,
    ):
        self.base_url = base_url
        self.init_url = init_url
        self.media_pattern = media_pattern
        self.start_number = start_number
        self.segments = segments
        self.mimetype = mimetype


def extract_qualities(mpd_text: str) -> List[Dict[str, str]]:
    """
    Extrae las calidades disponibles (audio y video) desde el contenido del MPD.
    """
    ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
    root = ET.fromstring(mpd_text)

    qualities = []
    for aset in root.findall(".//mpd:AdaptationSet", ns):
        for rep in aset.findall("mpd:Representation", ns):
            qualities.append(
                {
                    "representation_id": rep.attrib.get("id", ""),
                    "width": rep.attrib.get("width", ""),
                    "height": rep.attrib.get("height", ""),
                    "bandwidth": rep.attrib.get("bandwidth", ""),
                    "mimeType": aset.attrib.get("mimeType", ""),
                }
            )
    return qualities


def extract_representation_info(xml_text: str, representation_id: str) -> MPDInfo:
    """
    Parsea el MPD y devuelve la información detallada de una representación específica.
    """
    ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
    root = ET.fromstring(xml_text)

    base_url_element = root.find("mpd:BaseURL", ns)
    base_url = base_url_element.text if base_url_element is not None else ""

    for aset in root.findall(".//mpd:AdaptationSet", ns):
        for rep in aset.findall("mpd:Representation", ns):
            if rep.attrib.get("id") == representation_id:
                template = rep.find("mpd:SegmentTemplate", ns)
                timeline = template.find("mpd:SegmentTimeline", ns)

                init_url = base_url + template.attrib["initialization"]
                media_pattern = base_url + template.attrib["media"]

                segments = []
                for s in timeline.findall("mpd:S", ns):
                    repeat = int(s.attrib.get("r", 0))
                    segments.extend([s] * (repeat + 1))

                return MPDInfo(
                    base_url=base_url,
                    init_url=init_url,
                    media_pattern=media_pattern,
                    start_number=int(template.attrib["startNumber"]),
                    segments=segments,
                    mimetype=aset.attrib.get("mimeType", ""),
                )

    raise ValueError(f"No se encontró Representation ID {representation_id}")
