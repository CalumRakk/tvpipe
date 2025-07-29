from proyect_x.ditu.api.dash import Dash
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule

from .api.channel import DituChannel
from .api.schedule import DituSchedule


class DituStream:
    def __init__(self):
        self.schedule = DituSchedule()
        self.channel = DituChannel()
        self.dash = Dash()

    def get_schedule(self, channel) -> list[SimpleSchedule]:
        """Obtiene la programación del dia de un canal de la TV.

        Args:
            channel (int | str): ID o nombre del canal de la TV. Un string hace una busqueda por nombre que no distingue entre mayúsculas y minúsculas ni tildres, mientras un int hace una busqueda por id

        Returns:
            list[SimpleSchedule]: Programación del dia de un canal de la TV.

        """
        is_string = True if isinstance(channel, str) else False
        if is_string:
            return self.schedule.get_schedule_by_name(channel)
        else:
            return self.schedule.get_schedule_by_id(int(channel))
