"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务"""

from PIL import Image

from src.image_utils import crop_face_to_square, image_to_data_url


def test_crop_face_to_square_falls_back_to_center_crop():
    image = Image.new("RGB", (800, 600), color=(255, 255, 255))
    result = crop_face_to_square(image, (512, 512))
    assert result.size == (512, 512)


def test_image_to_data_url_returns_png_data_url():
    image = Image.new("RGB", (32, 32), color=(240, 240, 240))
    result = image_to_data_url(image)
    assert result.startswith("data:image/png;base64,")
