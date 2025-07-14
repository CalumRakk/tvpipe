from pathlib import Path
from typing import Union, cast

import cv2
from PIL import Image, ImageDraw, ImageFont


def extract_first_frame(
    video_path: Union[str, Path], output_image: Union[str, Path]
) -> Path:
    """Extrae el primer frame del video y lo guarda como imagen."""
    video_path = Path(video_path)
    output_image = Path(output_image)

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("❌ No se pudo leer el primer frame.")

    cv2.imwrite(str(output_image), frame)
    print(f"✅ Primer frame guardado en: {output_image}")
    return output_image


def load_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    """Carga una fuente personalizada o usa la fuente por defecto."""
    try:
        font = ImageFont.truetype(font_path, font_size)
        print(f"✅ Fuente cargada: {font_path}")
        return font
    except IOError:
        print(
            f"❌ No se pudo cargar la fuente '{font_path}'. Usando fuente por defecto."
        )
        return cast(ImageFont.FreeTypeFont, ImageFont.load_default())


def create_watermark_layer(
    base_image: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    margin: int = 20,
    bg_padding: int = 10,
    bg_opacity: int = 128,
) -> Image.Image:
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
    bg_x0 = base_image.width - bg_width - margin
    bg_y0 = base_image.height - bg_height - margin
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
        draw.text((text_x + 2, text_y + 2), text, font=font, fill="black", anchor="lt")
        draw.text((text_x, text_y), text, font=font, fill="white", anchor="lt")
    except TypeError:
        manual_x = text_x - bbox[0]
        manual_y = text_y - bbox[1]
        draw.text((manual_x + 2, manual_y + 2), text, font=font, fill="black")
        draw.text((manual_x, manual_y), text, font=font, fill="white")

    return txt_layer


def add_watermark(
    image_path: Union[str, Path],
    watermark_text: str,
    font: ImageFont.FreeTypeFont,
    output_path: Union[str, Path],
) -> None:
    """Agrega una marca de agua a una imagen y la guarda."""
    image = Image.open(image_path).convert("RGBA")
    print(f"✅ Imagen base '{image_path}' cargada.")

    watermark_layer = create_watermark_layer(image, watermark_text, font)
    watermarked = Image.alpha_composite(image, watermark_layer)

    watermarked.convert("RGB").save(output_path, "JPEG")
    print(f"✅ Imagen final guardada como '{output_path}'")


def main():
    # -------- CONFIGURACIÓN --------
    video_path = r"D:\github Leo\caracoltv-dl\output\desafio.siglo.xxi.2025.capitulo.07.yt.720p.mp4"
    output_image = "thumbnail_watermarked.jpg"
    watermark_text = "t.me/eldesafio2"
    font_path = (
        r"D:\github Leo\caracoltv-dl\fonts\Roboto\Roboto-VariableFont_wdth,wght.ttf"
    )
    font_size = 48

    font = load_font(font_path, font_size)
    frame_image = extract_first_frame(video_path, output_image)
    add_watermark(frame_image, watermark_text, font, output_image)


if __name__ == "__main__":
    main()
