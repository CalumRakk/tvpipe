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
        self.schedule = DituSchedule()
        self.channel = DituChannel()

    def get_current_program_live(self, channel_id: int) -> FilterResponse:
        """Obtiene informacion del programa actualmente en emision de un canal."""
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/SEARCH/PROGRAM"
        params = {
            "filter_channelIds": str(channel_id),
            "filter_airingTime": "now",
        }
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        return response.json()

    def _get_entitlements_for_live_channel(
        self, channel_id: int
    ) -> EntitlementChannelResponse:
        """Obtiene la información de derechos de reproducción ("entitlement") y los assets disponibles (por ejemplo, LIVE_HD) para una transmisión en vivo del canal especificado. Sirve para determinar si el canal puede reproducirse y qué assets están disponibles, incluyendo su assetId, que puede usarse en otro endpoint (como el de VIDEOURL).

        Nota: No se usa de momento.
        """
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/USERDATA/LIVE/20"
        params = {
            "filter_channelIds": str(channel_id),
            "filter_entitlementType": "live",
        }
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        return response.json()

    def _get_dash_manifest_for_live_channel(
        self, channel_id: Union[str, int]
    ) -> DashManifestResponse:
        """Obtiene un JSON con la URL del DASH manifest para la transmision en vivo del canal especificado."""
        url = f"https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/VIDEOURL/LIVE/{channel_id}/10"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()

    def _get_manifest_url(self, channel_id: Union[str, int]) -> str:
        """
        Recupera la URL del manifiesto DASH para un canal en vivo.
        """
        response = self._get_dash_manifest_for_live_channel(str(channel_id))
        return response["resultObj"]["src"]

    def get_representation_info(self, mpd_text: str, rep_id: str) -> MPDInfo:
        """
        Extrae la información de una representación específica dentro del MPD.
        """
        return extract_representation_info(mpd_text, rep_id)

    # def download_representation(self, rep_info: MPDInfo, output_folder: Path) -> None:
    #     """
    #     Descarga todos los segmentos (inicial + medios) de una representación del MPD.
    #     """
    #     mime, ext = rep_info.mimetype.split("/")
    #     dest_folder = output_folder / mime
    #     dest_folder.mkdir(parents=True, exist_ok=True)

    #     # Descargar segmento inicial
    #     init_path = dest_folder / f"init.{ext}"
    #     if not init_path.exists():
    #         download_file(rep_info.init_url, init_path)

    #     # Descargar segmentos medios
    #     for idx, _ in enumerate(rep_info.segments):
    #         seg_num = rep_info.start_number + idx
    #         seg_url = rep_info.media_pattern.replace("$Number$", str(seg_num))
    #         seg_filename = Path(seg_url).name
    #         seg_path = dest_folder / seg_filename

    #         if not seg_path.exists():
    #             download_file(seg_url, seg_path)

    def get_available_qualities(self, mpd_text: str) -> List[Dict[str, str]]:
        """
        Extrae las calidades disponibles desde el MPD.
        """
        return extract_qualities(mpd_text)

    # def get_best_representation_for_live_channel(self, channel_id: int) -> MPDInfo:
    #     mpd_url = self._get_manifest_url(channel_id)
