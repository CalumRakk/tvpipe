from typing import Union

import requests

from ditu._live_dash_downloader import HEADERS
from proyect_x.ditu.api.parser import extract_qualities
from proyect_x.ditu.schemas.dashmanifest_response import DashManifestResponse
from proyect_x.ditu.schemas.entitlement_response import EntitlementChannelResponse


class Dash:

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

    def get_live_channel_manifest(self, channel_id: Union[str, int]) -> str:
        """Obtiene un JSON con la URL del DASH manifest para la transmision en vivo del canal especificado."""
        url = f"https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/VIDEOURL/LIVE/{channel_id}/10"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()

        data: DashManifestResponse = response.json()
        return data["resultObj"]["src"]

    def fetch_mpd(self, url: str) -> str:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text

    def _extract_qualities(self, mpd_text: str) -> list:
        """
        Extrae las calidades disponibles desde el MPD.
        """
        return extract_qualities(mpd_text)
