import os
from datetime import datetime

from yt_dlp import DownloadError, YoutubeDL

# === Configuración ===

# yt-dlp --live-from-start -f best -o "%(title)s.%(ext)s" https://www.youtube.com/watch?v=2ZYP2p4fQrw

# Carpeta base de salida
base_output_dir = "live_downloads"
ydl_opts_base = {
    "url": "https://www.youtube.com/watch?v=2ZYP2p4fQrw",
    "live_from_start": True,
    "hls_use_mpegts": True,
    "hls_prefer_ffmpeg": True,
    "outtmpl": "%(upload_date)s_%(title)s.%(ext)s",
    "noplaylist": True,
    "ignoreerrors": False,
    "retries": 3,
}

# === Lógica de descarga ===

url = ydl_opts_base["url"]
# Carpeta de salida única por fecha
date_prefix = datetime.now().strftime("%Y-%m-%d")
output_template = os.path.join(base_output_dir, date_prefix, ydl_opts_base["outtmpl"])

ydl_opts = ydl_opts_base.copy()
ydl_opts["outtmpl"] = output_template

print(f"Descargando: {url}")
print(f"Salida: {output_template}")

try:
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(f"✅ Descarga completada: {url}")
except DownloadError as e:
    print(f"❌ Error al descargar {url}: {str(e)}")
except Exception as e:
    print(f"⚠️ Error inesperado: {str(e)}")

print("🚩 Todos los trabajos terminaron.")
