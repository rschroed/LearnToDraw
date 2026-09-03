from __future__ import annotations

import json

import httpx
import pytest

from learn_to_draw_api.models import InvalidArtifactError
from learn_to_draw_api.services.drawing_advisor import OpenAIDrawingAdvisor
from learn_to_draw_api.services.drawing_sessions import (
    validate_and_normalize_advisor_svg,
)


def _svg(width: float = 170, height: float = 257, child: str | None = None) -> str:
    child = child or '<circle cx="85" cy="128" r="10" />'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" '
        f'height="{height}mm" viewBox="0 0 {width} {height}">{child}</svg>'
    )


def test_advisor_svg_is_normalized_to_safe_plot_styling():
    normalized = validate_and_normalize_advisor_svg(
        _svg(),
        drawable_width_mm=170,
        drawable_height_mm=257,
    )

    assert 'fill="none"' in normalized
    assert 'stroke="black"' in normalized
    assert 'stroke-width="0.6"' in normalized


@pytest.mark.parametrize(
    ("svg_text", "message"),
    [
        (_svg(width=180), "exactly match"),
        (_svg(child='<circle cx="185" cy="128" r="10" />'), "outside"),
        (_svg(child='<script>alert(1)</script>'), "not allowed"),
        (_svg(child='<image href="https://example.test/a.png" />'), "not allowed"),
        (_svg(child='<g transform="rotate(45)"><circle cx="85" cy="128" r="10" /></g>'), "not allowed"),
    ],
)
def test_advisor_svg_rejects_unsafe_or_unbounded_output(svg_text, message):
    with pytest.raises(InvalidArtifactError, match=message):
        validate_and_normalize_advisor_svg(
            svg_text,
            drawable_width_mm=170,
            drawable_height_mm=257,
        )


def test_openai_advisor_sends_registered_image_and_parses_structured_output(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "interpretation": "Add more variation.",
                                        "svg": _svg(),
                                    }
                                ),
                            }
                        ],
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    advisor = OpenAIDrawingAdvisor(api_key="secret", model="vision-model")

    result = advisor.propose_next_layer(
        intent="A field of flowers",
        observed_image=b"png-bytes",
        observed_media_type="image/png",
        iteration_number=1,
        iteration_limit=3,
        drawable_width_mm=170,
        drawable_height_mm=257,
        prior_interpretations=[],
    )

    assert result.interpretation == "Add more variation."
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["json"]["store"] is False
    assert captured["json"]["text"]["format"]["type"] == "json_schema"
    image_input = captured["json"]["input"][0]["content"][1]
    assert image_input["image_url"].startswith("data:image/png;base64,")
    assert "secret" not in json.dumps(captured["json"])
