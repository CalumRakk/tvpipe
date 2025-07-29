from pathlib import Path
from typing import Dict, List, Union

import requests

from proyect_x.ditu.api.channel import DituChannel
from proyect_x.ditu.schemas.dashmanifest_response import DashManifestResponse
from proyect_x.ditu.schemas.entitlement_response import EntitlementChannelResponse
from proyect_x.ditu.schemas.filder_response import FilterResponse

from .parser import MPDInfo, extract_qualities, extract_representation_info
from .schedule import HEADERS, DituSchedule


class DituStream:
    """
    Clase especializada que extiende `Ditu` para manejar transmisiones DASH (MPD),
    incluyendo extracción de representaciones y descarga de segmentos.
    """

    def __init__(self):
    def get_representation_info(self, mpd_text: str, rep_id: str) -> MPDInfo:
        """
        Extrae la información de una representación específica dentro del MPD.
        """
        return extract_representation_info(mpd_text, rep_id)

    def download_representation(self, rep_info: MPDInfo, output_folder: Path) -> None:
        """
        Descarga todos los segmentos (inicial + medios) de una representación del MPD.
        """
        mime, ext = rep_info.mimetype.split("/")
        dest_folder = output_folder / mime
        dest_folder.mkdir(parents=True, exist_ok=True)

        # Descargar segmento inicial
        init_path = dest_folder / f"init.{ext}"
        if not init_path.exists():
            download_file(rep_info.init_url, init_path)

        # Descargar segmentos medios
        for idx, _ in enumerate(rep_info.segments):
            seg_num = rep_info.start_number + idx
            seg_url = rep_info.media_pattern.replace("$Number$", str(seg_num))
            seg_filename = Path(seg_url).name
            seg_path = dest_folder / seg_filename

            if not seg_path.exists():
                download_file(seg_url, seg_path)
