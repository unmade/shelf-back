from pi_heif import HeifImagePlugin  # noqa
from PIL import ImageFile, Image

from .config import config

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = config.features.max_image_pixels
