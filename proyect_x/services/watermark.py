import logging
from importlib.resources import as_file, files
from pathlib import Path
from typing import Union, cast

from PIL import Image, ImageDraw, ImageFont

from .. import assets

logger = logging.getLogger(__name__)


class WatermarkService:
    def __init__(
        self,
        font_name: str = "Roboto-VariableFont_wdth,wght.ttf",
        default_size: int = 48,
    ):
        self.font_name = font_name
        self.default_size = default_size
        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}

    def _load_bundled_font(self, font_size: int) -> ImageFont.FreeTypeFont:
        if font_size in self._font_cache:
            return self._font_cache[font_size]

        try:
            # Asumimos que dentro de 'assets' hay una carpeta 'fonts'.
            font_resource = files(assets).joinpath("fonts", self.font_name)  # type: ignore

            with as_file(font_resource) as font_path:
                logger.debug(f"Cargando fuente desde recurso: {font_path}")
                font = ImageFont.truetype(str(font_path), font_size)
                self._font_cache[font_size] = font
                return font
        except (ImportError, FileNotFoundError, OSError) as e:
            logger.warning(f"No se pudo cargar la fuente interna: {e}. Usando default.")
            return cast(ImageFont.FreeTypeFont, ImageFont.load_default())

    def add_watermark_to_image(
        self, input_path: Union[str, Path], text: str, output_path: Union[str, Path]
    ) -> Path:
        input_path = Path(input_path)
        output_path = Path(output_path)

        font = self._load_bundled_font(self.default_size)

        try:
            with Image.open(input_path).convert("RGBA") as base_image:
                # 1. Capturamos la capa de texto generada
                watermark_layer = self._apply_watermark_layer(base_image, text, font)

                # 2. Fusionamos la imagen base con la capa de texto
                final_image = Image.alpha_composite(base_image, watermark_layer)

                output_path.parent.mkdir(parents=True, exist_ok=True)

                # 3. Guardamos la imagen resultante
                final_image.convert("RGB").save(output_path, "JPEG")

        except Exception as e:
            logger.error(f"Error procesando imagen {input_path}: {e}")
            raise

        return output_path

    def _apply_watermark_layer(
        self,
        base_image: Image.Image,
        text: str,
        font: ImageFont.FreeTypeFont,
        bg_padding: int = 10,
        bg_opacity: int = 128,
        vertical_offset: int = 165,
        horizontal_offset: int = 215,
        margin: int = 20,
        color="yellow",
    ):
        """Crea una capa de marca de agua con texto y fondo."""
        txt_layer = Image.new("RGBA", base_image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # Calcular tamaño del texto
        try:
            bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
        except TypeError:
            bbox = draw.textbbox((0, 0), text, font=font)

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Tamaño y posición del fondo
        bg_width = text_width + bg_padding * 2
        bg_height = text_height + bg_padding * 2
        bg_x0 = base_image.width - bg_width - margin - horizontal_offset
        bg_y0 = base_image.height - bg_height - margin - vertical_offset
        bg_x1 = bg_x0 + bg_width
        bg_y1 = bg_y0 + bg_height

        # Fondo semi-transparente
        rect_color = (0, 0, 0, bg_opacity)
        draw.rounded_rectangle([bg_x0, bg_y0, bg_x1, bg_y1], radius=10, fill=rect_color)

        # Posición del texto
        text_x = bg_x0 + bg_padding
        text_y = bg_y0 + bg_padding

        # Dibujar sombra y texto
        try:
            draw.text(
                (text_x + 2, text_y + 2), text, font=font, fill="black", anchor="lt"
            )
            draw.text((text_x, text_y), text, font=font, fill=color, anchor="lt")
        except TypeError:
            manual_x = text_x - bbox[0]
            manual_y = text_y - bbox[1]
            draw.text((manual_x + 2, manual_y + 2), text, font=font, fill="black")
            draw.text((manual_x, manual_y), text, font=font, fill=color)

        return txt_layer
