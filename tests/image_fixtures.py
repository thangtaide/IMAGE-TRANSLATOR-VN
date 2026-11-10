"""Visible raster ink for provider stubs; this is not an OCR accuracy fixture."""
from PIL import Image, ImageDraw, ImageFont
from core.imaging import default_font


def provider_page(size, marker):
    image = Image.new('RGB',size,(marker,marker,marker))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(default_font()),18)
    for y in range(24,size[1]-20,40):
        draw.text((30,y),'Fixture text',font=font,fill='white')
    return image
