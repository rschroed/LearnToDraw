from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
import json
from typing import Optional

import httpx

from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import DrawingAdvisorStatus, ServiceUnavailableError


@dataclass(frozen=True)
class DrawingAdviceDraft:
    interpretation: str
    svg_text: str


class DrawingAdvisor(ABC):
    @property
    @abstractmethod
    def status(self) -> DrawingAdvisorStatus:
        raise NotImplementedError

    @abstractmethod
    def propose_next_layer(
        self,
        *,
        intent: str,
        observed_image: bytes,
        observed_media_type: str,
        iteration_number: int,
        iteration_limit: int,
        drawable_width_mm: float,
        drawable_height_mm: float,
        prior_interpretations: list[str],
    ) -> DrawingAdviceDraft:
        raise NotImplementedError


class DisabledDrawingAdvisor(DrawingAdvisor):
    @property
    def status(self) -> DrawingAdvisorStatus:
        return DrawingAdvisorStatus(
            driver="disabled",
            available=False,
            message=(
                "Drawing advisor is disabled. Set LEARN_TO_DRAW_DRAWING_ADVISOR=openai, "
                "OPENAI_API_KEY, and LEARN_TO_DRAW_OPENAI_MODEL to enable it."
            ),
        )

    def propose_next_layer(self, **_kwargs) -> DrawingAdviceDraft:
        raise ServiceUnavailableError(self.status.message or "Drawing advisor is unavailable.")


class MockDrawingAdvisor(DrawingAdvisor):
    @property
    def status(self) -> DrawingAdvisorStatus:
        return DrawingAdvisorStatus(driver="mock", available=True, model="mock-advisor-v1")

    def propose_next_layer(
        self,
        *,
        intent: str,
        iteration_number: int,
        drawable_width_mm: float,
        drawable_height_mm: float,
        **_kwargs,
    ) -> DrawingAdviceDraft:
        center_x = round(drawable_width_mm / 2, 3)
        center_y = round(drawable_height_mm / 2, 3)
        radius = round(min(drawable_width_mm, drawable_height_mm) * 0.08, 3)
        svg_text = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{drawable_width_mm}mm" height="{drawable_height_mm}mm" '
            f'viewBox="0 0 {drawable_width_mm} {drawable_height_mm}">'
            f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" '
            'fill="none" stroke="black" stroke-width="0.6"/>'
            "</svg>"
        )
        return DrawingAdviceDraft(
            interpretation=(
                f'Mock observation for “{intent}” after iteration {iteration_number}: '
                "add one simple focal contour near the center."
            ),
            svg_text=svg_text,
        )


class OpenAIDrawingAdvisor(DrawingAdvisor):
    def __init__(self, *, api_key: Optional[str], model: Optional[str]) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def status(self) -> DrawingAdvisorStatus:
        missing = []
        if not self._api_key:
            missing.append("OPENAI_API_KEY")
        if not self._model:
            missing.append("LEARN_TO_DRAW_OPENAI_MODEL")
        return DrawingAdvisorStatus(
            driver="openai",
            available=not missing,
            model=self._model,
            message=f"Missing {', '.join(missing)}." if missing else None,
        )

    def propose_next_layer(
        self,
        *,
        intent: str,
        observed_image: bytes,
        observed_media_type: str,
        iteration_number: int,
        iteration_limit: int,
        drawable_width_mm: float,
        drawable_height_mm: float,
        prior_interpretations: list[str],
    ) -> DrawingAdviceDraft:
        if not self.status.available or not self._api_key or not self._model:
            raise ServiceUnavailableError(
                self.status.message or "OpenAI drawing advisor is not configured."
            )
        history = "\n".join(
            f"- {item}" for item in prior_interpretations[-5:]
        ) or "- No earlier interpretations."
        prompt = (
            f"Drawing intent: {intent}\n"
            f"Completed iteration: {iteration_number} of {iteration_limit}\n"
            f"Drawable SVG canvas: {drawable_width_mm} mm wide by "
            f"{drawable_height_mm} mm high.\n"
            f"Earlier interpretations:\n{history}\n\n"
            "Interpret the photographed physical drawing for visual appeal and progress toward "
            "the intent. Propose only an additive next layer: new black stroked vector marks that "
            "can be plotted over the existing sheet. Do not redraw the full existing composition, "
            "erase, fill a background, include text, or optimize for pixel-identical replication. "
            "The SVG root width and height must exactly match the drawable canvas in mm, its "
            "viewBox must start at 0 0 with those same dimensions, and every mark must remain "
            "inside that viewBox. Use only svg, g, path, line, polyline, polygon, circle, ellipse, "
            "and rect elements. Use direct coordinates without transform attributes. Use "
            "fill=none and black strokes."
        )
        encoded_image = base64.b64encode(observed_image).decode("ascii")
        payload = {
            "model": self._model,
            "store": False,
            "instructions": (
                "You are the read-only visual drawing advisor inside a local pen-plotter system. "
                "You may return interpretation and SVG data only; you cannot control hardware."
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{observed_media_type};base64,{encoded_image}"
                            ),
                            "detail": "high",
                        },
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "drawing_advice",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "interpretation": {"type": "string"},
                            "svg": {"type": "string"},
                        },
                        "required": ["interpretation", "svg"],
                        "additionalProperties": False,
                    },
                }
            },
            "max_output_tokens": 6000,
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            response_payload = response.json()
            output_text = _extract_output_text(response_payload)
            parsed = json.loads(output_text)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ServiceUnavailableError(
                f"Drawing advisor request failed: {exc}"
            ) from exc
        interpretation = parsed.get("interpretation")
        svg_text = parsed.get("svg")
        if not isinstance(interpretation, str) or not isinstance(svg_text, str):
            raise ServiceUnavailableError(
                "Drawing advisor returned an incomplete structured response."
            )
        return DrawingAdviceDraft(
            interpretation=interpretation.strip(),
            svg_text=svg_text.strip(),
        )


def _extract_output_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str) and text:
                    return text
    raise ValueError("Response did not contain output text.")


def build_drawing_advisor(config: AppConfig) -> DrawingAdvisor:
    if config.drawing_advisor_driver == "mock":
        return MockDrawingAdvisor()
    if config.drawing_advisor_driver == "openai":
        return OpenAIDrawingAdvisor(
            api_key=config.openai_api_key,
            model=config.openai_model,
        )
    if config.drawing_advisor_driver != "disabled":
        raise ValueError(
            "LEARN_TO_DRAW_DRAWING_ADVISOR must be disabled, mock, or openai."
        )
    return DisabledDrawingAdvisor()
