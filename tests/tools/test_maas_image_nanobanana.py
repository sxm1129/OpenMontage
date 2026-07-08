"""Regression: maas_image must build a different payload shape for
gemini-3.1-flash-image-preview ("NanoBanana") vs leapfast/flux2, per
docs/multimodal-call-guide-v4.md — NanoBanana takes a ratio-style `size`
("16x9") and a `quality` tier, and its image-to-image reference is a URL
array (`images`), the inverse of flux2's base64 `input_image`.
"""

from __future__ import annotations

from tools.graphics.maas_image import MaasImage


def test_flux2_default_size_is_pixel_dimensions():
    tool = MaasImage()
    payload = tool._build_payload({"prompt": "a cat"})
    assert payload["model"] == "leapfast/flux2"
    assert payload["size"] == "1024x1024"
    assert "quality" not in payload


def test_nanobanana_default_size_is_ratio_not_pixel_dimensions():
    tool = MaasImage()
    payload = tool._build_payload({
        "prompt": "a cat",
        "model": "gemini-3.1-flash-image-preview",
    })
    assert payload["size"] == "16x9"
    assert payload["quality"] == "1K"


def test_nanobanana_reference_images_map_to_images_field():
    tool = MaasImage()
    payload = tool._build_payload({
        "prompt": "a cat",
        "model": "gemini-3.1-flash-image-preview",
        "reference_images": ["https://example.com/a.png", "https://example.com/b.png"],
    })
    assert payload["images"] == ["https://example.com/a.png", "https://example.com/b.png"]
    assert "input_image" not in payload


def test_flux2_input_image_passed_through_as_base64_not_url_field():
    tool = MaasImage()
    payload = tool._build_payload({
        "prompt": "a cat",
        "input_image": "data:image/png;base64,AAAA",
    })
    assert payload["input_image"] == "data:image/png;base64,AAAA"
    assert "images" not in payload


def test_nanobanana_registered_in_models_catalogue():
    assert "gemini-3.1-flash-image-preview" in MaasImage.MODELS
