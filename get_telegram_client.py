import time
from os import getenv
from pathlib import Path
from platform import system

from pyrogram import Client

from config import API_HASH, API_ID, CHAT_ID, PROJECT_NAME

API_HASH = API_HASH
API_ID = API_ID
CHAT_ID = CHAT_ID

HOME = Path.home() / ".local/share" if system() == "Linux" else Path(getenv("APPDATA"))  # type: ignore
WORKTABLE = HOME / PROJECT_NAME

client = Client(
    "leo",
    api_id=API_ID,
    api_hash=API_HASH,
    workdir=str(WORKTABLE),
)
client.start()

for message in client.get_chat_history(CHAT_ID):
    if message.caption is None:
        continue

    if "Desafío The Box 2022" in message.caption and not ("#" in message.caption):
        new_caption = message.caption + "\n\n#Desafío #Desafío2022 #TheBox2"
        client.edit_message_caption(CHAT_ID, message.id, new_caption)  # type: ignore

    time.sleep(0.5)
