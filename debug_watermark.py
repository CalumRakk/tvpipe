from proyect_x.services.watermark import WatermarkService

water = WatermarkService()

water.add_watermark_to_image(
    "thumbnail_watermarked.jpg", "HOLA MUNDO", "thumbnail_watermarked_TEST.jpg"
)
