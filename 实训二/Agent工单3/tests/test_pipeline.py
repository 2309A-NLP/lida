"""工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务"""

from src.pipeline import StableDiffusionFaceTurnAgent


def test_extract_image_url_supports_legacy_results_payload():
    payload = {"output": {"results": [{"url": "https://example.com/a.png"}]}}
    assert StableDiffusionFaceTurnAgent._extract_image_url(payload) == "https://example.com/a.png"


def test_extract_image_url_supports_multimodal_choices_payload():
    payload = {
        "output": {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "image", "image": "https://example.com/b.png"},
                        ]
                    }
                }
            ]
        }
    }
    assert StableDiffusionFaceTurnAgent._extract_image_url(payload) == "https://example.com/b.png"
