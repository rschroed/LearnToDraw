from __future__ import annotations

import base64
import json
from threading import Event, Thread

import cv2
import httpx
import numpy as np
import pytest

from learn_to_draw_api.models import InvalidArtifactError, ServiceUnavailableError
from learn_to_draw_api.services.drawing_advisor import (
    OPENAI_REQUEST_TIMEOUT_SECONDS,
    OpenAIDrawingAdvisor,
    RuntimeDrawingAdvisor,
)
from learn_to_draw_api.services.drawing_sessions import (
    validate_and_normalize_advisor_svg,
)


CREATIVE_CRITERIA = [
    "Make the pose playful and observational.",
    "Use loose sketchbook linework.",
    "Keep the bicycle and pelican readable.",
]


def _criterion_assessments(outcome: str = "meets") -> list[dict]:
    return [
        {
            "rank": index,
            "outcome": outcome,
            "assessment": f"Criterion {index} assessment.",
        }
        for index in range(1, len(CREATIVE_CRITERIA) + 1)
    ]


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
    assert captured["timeout"] == OPENAI_REQUEST_TIMEOUT_SECONDS
    image_input = captured["json"]["input"][0]["content"][1]
    assert image_input["image_url"].startswith("data:image/png;base64,")
    assert "secret" not in json.dumps(captured["json"])


def test_openai_advisor_plans_first_pass_without_an_image(monkeypatch):
    captured = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": json.dumps(self._payload)}

    def fake_post(url, **kwargs):
        captured.append({"url": url, **kwargs})
        schema_name = kwargs["json"]["text"]["format"]["name"]
        if schema_name == "initial_drawing_plan":
            return Response(
                {
                    "summary": "Begin with the pelican and bicycle silhouette.",
                    "paper_strategy": "Keep the same sheet in place.",
                    "completion_intent": "Stop when the gesture reads clearly.",
                    "creative_criteria": CREATIVE_CRITERIA,
                    "svg": _svg(),
                }
            )
        return Response(
            {
                "summary": "The candidate is a sound first layer.",
                "decision": "accept",
                "criterion_assessments": _criterion_assessments(),
                "svg": None,
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    advisor = OpenAIDrawingAdvisor(api_key="secret", model="vision-model")

    result = advisor.plan_initial(
        intent="A pelican riding a bicycle",
        guidance=["Keep it loose."],
        drawable_width_mm=170,
        drawable_height_mm=257,
    )

    assert result.summary.startswith("Begin with")
    assert result.creative_criteria == CREATIVE_CRITERIA
    assert result.quality_review.decision == "accept"
    assert len(captured) == 2
    assert captured[0]["json"]["text"]["format"]["name"] == "initial_drawing_plan"
    assert captured[0]["json"]["input"][0]["content"] == [
        {
            "type": "input_text",
            "text": captured[0]["json"]["input"][0]["content"][0]["text"],
        }
    ]
    review_image = captured[1]["json"]["input"][0]["content"][1]
    assert review_image["image_url"].startswith("data:image/png;base64,")
    png_bytes = base64.b64decode(review_image["image_url"].split(",", 1)[1])
    rendered = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert rendered.shape[:2] == (1600, 1058)
    assert rendered[0, 0].tolist() == [255, 255, 255]
    assert all(item["timeout"] == OPENAI_REQUEST_TIMEOUT_SECONDS for item in captured)


def test_openai_advisor_applies_one_review_revision(monkeypatch):
    candidate = _svg(child='<circle cx="85" cy="128" r="10" />')
    replacement = _svg(child='<circle cx="70" cy="118" r="16" />')
    payloads = [
        {
            "summary": "Start with an observational gesture.",
            "paper_strategy": "Keep generous margins.",
            "completion_intent": "Stop when the page feels studied rather than diagrammed.",
            "creative_criteria": CREATIVE_CRITERIA,
            "svg": candidate,
        },
        {
            "summary": "The first candidate is too diagrammatic, so it was replaced.",
            "decision": "revise",
            "criterion_assessments": _criterion_assessments("misses"),
            "svg": replacement,
        },
    ]
    requests = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": json.dumps(self._payload)}

    def fake_post(_url, **kwargs):
        requests.append(kwargs["json"])
        return Response(payloads.pop(0))

    monkeypatch.setattr(httpx, "post", fake_post)
    advisor = OpenAIDrawingAdvisor(api_key="secret", model="vision-model")

    result = advisor.plan_initial(
        intent="A scientific dragonfly in a loose sketchbook style",
        guidance=[],
        drawable_width_mm=170,
        drawable_height_mm=257,
    )

    assert len(requests) == 2
    assert result.quality_review.decision == "revise"
    assert result.quality_review.revision_applied is True
    assert 'cx="70"' in result.svg_text
    assert 'cx="85"' not in result.svg_text
    review_prompt = requests[1]["input"][0]["content"][0]["text"]
    assert "merely recognizable subject does not compensate" in review_prompt


def test_openai_advisor_rejects_unsafe_review_revision(monkeypatch):
    payloads = [
        {
            "summary": "Start with an observational gesture.",
            "paper_strategy": "Keep generous margins.",
            "completion_intent": "Stop when the study feels convincing.",
            "creative_criteria": CREATIVE_CRITERIA,
            "svg": _svg(),
        },
        {
            "summary": "Replace the generic candidate.",
            "decision": "revise",
            "criterion_assessments": _criterion_assessments("misses"),
            "svg": _svg(child='<script>alert(1)</script>'),
        },
    ]

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": json.dumps(payloads.pop(0))}

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response())
    advisor = OpenAIDrawingAdvisor(api_key="secret", model="vision-model")

    with pytest.raises(InvalidArtifactError, match="not allowed"):
        advisor.plan_initial(
            intent="A scientific dragonfly in a loose sketchbook style",
            guidance=[],
            drawable_width_mm=170,
            drawable_height_mm=257,
        )


def test_openai_advisor_reports_actionable_timeout(monkeypatch):
    def time_out(*_args, **_kwargs):
        raise httpx.ReadTimeout(
            "The read operation timed out",
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx, "post", time_out)
    advisor = OpenAIDrawingAdvisor(api_key="secret", model="vision-model")

    with pytest.raises(
        ServiceUnavailableError,
        match=(
            rf"timed out after {OPENAI_REQUEST_TIMEOUT_SECONDS} seconds.*"
            "faster model in Controls"
        ),
    ):
        advisor.plan_initial(
            intent="A detailed dragonfly study",
            guidance=[],
            drawable_width_mm=170,
            drawable_height_mm=257,
        )


def test_runtime_model_update_does_not_mutate_an_inflight_advisor(monkeypatch):
    first_request_started = Event()
    release_first_request = Event()
    requested_models = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": json.dumps(self._payload)}

    def fake_post(_url, **kwargs):
        requested_models.append(kwargs["json"]["model"])
        if len(requested_models) == 1:
            first_request_started.set()
            release_first_request.wait(timeout=2)
        schema_name = kwargs["json"]["text"]["format"]["name"]
        if schema_name == "initial_drawing_plan":
            return Response(
                {
                    "summary": "Begin with a clear silhouette.",
                    "paper_strategy": "Keep the sheet registered.",
                    "completion_intent": "Stop before the page feels crowded.",
                    "creative_criteria": CREATIVE_CRITERIA,
                    "svg": _svg(),
                }
            )
        return Response(
            {
                "summary": "The candidate is ready.",
                "decision": "accept",
                "criterion_assessments": _criterion_assessments(),
                "svg": None,
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    advisor = RuntimeDrawingAdvisor(
        OpenAIDrawingAdvisor(api_key="secret", model="original-model")
    )
    completed = []
    worker = Thread(
        target=lambda: completed.append(
            advisor.plan_initial(
                intent="A scientific dragonfly",
                guidance=[],
                drawable_width_mm=170,
                drawable_height_mm=257,
            )
        )
    )

    worker.start()
    assert first_request_started.wait(timeout=1)
    updated = advisor.update_openai_model(model="new-model")
    release_first_request.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert len(completed) == 1
    assert requested_models == ["original-model", "original-model"]
    assert updated.advisor.model == "new-model"
    advisor.plan_initial(
        intent="A scientific dragonfly",
        guidance=[],
        drawable_width_mm=170,
        drawable_height_mm=257,
    )
    assert requested_models == [
        "original-model",
        "original-model",
        "new-model",
        "new-model",
    ]


def test_openai_advisor_assessment_requires_svg_for_continue(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": json.dumps(
                    {
                        "assessment": "The composition needs one more gesture.",
                        "decision": "continue",
                        "reason": "The bicycle does not read yet.",
                        "criterion_assessments": _criterion_assessments(
                            "partially_meets"
                        ),
                        "svg": _svg(),
                        "requested_human_action": None,
                    }
                )
            }

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response())
    advisor = OpenAIDrawingAdvisor(api_key="secret", model="vision-model")

    result = advisor.assess_iteration(
        intent="A pelican riding a bicycle",
        plan_summary="Start with the silhouette.",
        creative_criteria=CREATIVE_CRITERIA,
        observed_image=b"png-bytes",
        observed_media_type="image/png",
        iteration_number=1,
        drawable_width_mm=170,
        drawable_height_mm=257,
        prior_interpretations=[],
        guidance=["Make it playful."],
    )

    assert result.decision == "continue"
    assert result.svg_text == _svg()
    assert [item.criterion for item in result.criterion_assessments] == CREATIVE_CRITERIA
