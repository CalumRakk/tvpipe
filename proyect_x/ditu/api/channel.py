from typing import Optional

from unidecode import unidecode

from proyect_x.ditu.api.schedule import DituSchedule
from proyect_x.ditu.schemas.common import ChannelInfo


class DituChannel:
    def __init__(self):
        self.schedule = DituSchedule()

    def get_all_channel_info(self) -> list[ChannelInfo]:
        """
        Extrae información clave de todos los canales presentes en el archivo de programación.

        Retorna una lista de diccionarios con los campos:
        - channelId
        - channelName
        """
        canales = set()
        resultado = []
        raw_data = self.schedule._fetch_raw_channels_schedule()
        for canal in raw_data.get("resultObj", {}).get("containers", []):
            for emocion in canal.get("containers", []):
                channel = emocion.get("channel")
                if channel:
                    canal_id = channel.get("channelId")
                    canal_nombre = channel.get("channelName")
                    clave = (canal_id, canal_nombre)
                    if clave not in canales:
                        canales.add(clave)
                        resultado.append(
                            {"channelId": canal_id, "channelName": canal_nombre}
                        )
        return resultado

    def get_info(self, channel_name: str) -> ChannelInfo:
        """
        Obtiene la información del canal por su nombre.

        Args:
            channel_name: Nombre del canal a buscar.

        Returns:
            Un objeto ChannelInfo con la información del canal, o None si no se encuentra.
        """
        channels = self.get_all_channel_info()
        for channel in channels:
            if unidecode(channel_name.lower()) in unidecode(
                channel["channelName"].lower()
            ):
                return ChannelInfo(**channel)
        raise ValueError(f"El canal '{channel_name}' no fue encontrado.")
