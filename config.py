from pathlib import Path

from decouple import Config, RepositoryEnv

config = Config(repository=RepositoryEnv(".env"))


API_HASH = str(config("API_HASH"))
API_ID = int(config("API_ID"))
CHAT_ID = int(config("CHAT_ID"))
PROJECT_NAME = str(config("PROJECT_NAME"))
