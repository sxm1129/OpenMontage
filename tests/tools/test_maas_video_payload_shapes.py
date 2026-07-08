"""Regression: maas_video builds a different request shape per model family,
per docs/multimodal-call-guide-v4.md. Sending the wrong shape doesn't error —
it silently drops the reference image or trips an upstream 400 — so these
lock in the documented contract instead of relying on live-testing every
model family by hand.
"""

from __future__ import annotations

from tools.video.maas_video import MaasVideo


def test_seedance_image_to_video_uses_native_passthrough_and_drops_duration():
    tool = MaasVideo()
    payload, headers = tool._build_payload(
        "volcengine/doubao-seedance-2.0",
        "image_to_video",
        {"prompt": "a cat", "image_url": "https://example.com/cat.png", "duration_seconds": 5},
    )
    assert payload["model"] == "native/volcengine/doubao-seedance-2.0"
    assert "duration_seconds" not in payload, (
        "Volcengine rejects i2v/r2v with duration_seconds present (InvalidParameter 400)"
    )
    assert payload["content"][0] == {"type": "text", "text": "a cat"}
    assert payload["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/cat.png"},
    }
    assert headers == {"X-DLP-Passthrough": "true"}


def test_seedance_text_to_video_stays_standard_dto_with_duration():
    tool = MaasVideo()
    payload, headers = tool._build_payload(
        "volcengine/doubao-seedance-2.0",
        "text_to_video",
        {"prompt": "a cat", "duration_seconds": 5},
    )
    assert payload["model"] == "volcengine/doubao-seedance-2.0"
    assert payload["duration_seconds"] == 5
    assert "content" not in payload
    assert headers == {}


def test_happyhorse_i2v_uses_image_field_not_image_url():
    tool = MaasVideo()
    payload, _ = tool._build_payload(
        "happyhorse-1.0-i2v",
        "image_to_video",
        {"prompt": "a horse", "image_url": "https://example.com/horse.png"},
    )
    assert payload["image"] == "https://example.com/horse.png"
    assert "image_url" not in payload


def test_ltx_i2v_prefers_image_base64_over_image_url_and_sets_strength():
    tool = MaasVideo()
    payload, _ = tool._build_payload(
        "leapfast/ltx-2.3",
        "image_to_video",
        {
            "prompt": "a robot",
            "image_url": "https://example.com/robot.png",
            "image_base64": "data:image/png;base64,AAAA",
        },
    )
    # image_base64 wins and goes out under the `image` field name (per
    # LTX/Wan2.2's own priority: image_base64 > image > image_url).
    assert payload["image"] == "data:image/png;base64,AAAA"
    assert "image_url" not in payload
    assert payload["image_strength"] == 0.8


def test_wan22_drops_resolution_and_audio_uses_size_grid():
    tool = MaasVideo()
    payload, _ = tool._build_payload(
        "leapfast/wan2.2",
        "text_to_video",
        {"prompt": "waves", "aspect_ratio": "9:16"},
    )
    assert "resolution" not in payload
    assert "audio" not in payload
    assert payload["size"] == "704*1280"


def test_wan22_registered_with_correct_ops_and_no_audio_note():
    assert MaasVideo.MODELS["leapfast/wan2.2"]["ops"] == ["t2v", "i2v"]


def test_wan22_reference_to_video_rejected_not_supported():
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "waves",
        "model": "leapfast/wan2.2",
        "operation": "reference_to_video",
        "image_url": "https://example.com/x.png",
    })
    assert result.success is False
    assert "leapfast/wan2.2" in result.error
