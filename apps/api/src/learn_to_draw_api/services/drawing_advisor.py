from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
import json
from typing import Literal, Optional

import httpx

from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import DrawingAdvisorStatus, ServiceUnavailableError


@dataclass(frozen=True)
class DrawingAdviceDraft:
    interpretation: str
    svg_text: str


@dataclass(frozen=True)
class InitialDrawingPlanDraft:
    summary: str
    paper_strategy: str
    completion_intent: str
    svg_text: str


@dataclass(frozen=True)
class DrawingAssessmentDraft:
    assessment: str
    decision: Literal["continue", "complete", "pause"]
    reason: str
    svg_text: Optional[str] = None
    requested_human_action: Optional[str] = None


class DrawingAdvisor(ABC):
    @property
    @abstractmethod
    def status(self) -> DrawingAdvisorStatus:
        raise NotImplementedError

    @abstractmethod
    def plan_initial(
        self,
        *,
        intent: str,
        guidance: list[str],
        drawable_width_mm: float,
        drawable_height_mm: float,
    ) -> InitialDrawingPlanDraft:
        raise NotImplementedError

    @abstractmethod
    def assess_iteration(
        self,
        *,
        intent: str,
        plan_summary: str,
        observed_image: bytes,
        observed_media_type: str,
        iteration_number: int,
        drawable_width_mm: float,
        drawable_height_mm: float,
        prior_interpretations: list[str],
        guidance: list[str],
    ) -> DrawingAssessmentDraft:
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

    def plan_initial(self, **_kwargs) -> InitialDrawingPlanDraft:
        raise ServiceUnavailableError(self.status.message or "Drawing advisor is unavailable.")

    def assess_iteration(self, **_kwargs) -> DrawingAssessmentDraft:
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

    def plan_initial(
        self,
        *,
        intent: str,
        guidance: list[str],
        drawable_width_mm: float,
        drawable_height_mm: float,
    ) -> InitialDrawingPlanDraft:
        margin = round(min(drawable_width_mm, drawable_height_mm) * 0.18, 3)
        center_x = round(drawable_width_mm / 2, 3)
        center_y = round(drawable_height_mm / 2, 3)
        radius = round(min(drawable_width_mm, drawable_height_mm) * 0.12, 3)
        svg_text = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{drawable_width_mm}mm" height="{drawable_height_mm}mm" '
            f'viewBox="0 0 {drawable_width_mm} {drawable_height_mm}">'
            f'<circle cx="{center_x}" cy="{center_y}" r="{radius}"/>'
            f'<line x1="{margin}" y1="{center_y}" '
            f'x2="{drawable_width_mm - margin}" y2="{center_y}"/>'
            "</svg>"
        )
        return InitialDrawingPlanDraft(
            summary=f'Build “{intent}” from a simple focal gesture, then respond to the drawing.',
            paper_strategy="Keep the sheet in place and add restrained layers.",
            completion_intent="Stop when the subject reads clearly and the page still has breathing room.",
            svg_text=svg_text,
        )

    def assess_iteration(
        self,
        *,
        intent: str,
        iteration_number: int,
        drawable_width_mm: float,
        drawable_height_mm: float,
        guidance: list[str],
        **_kwargs,
    ) -> DrawingAssessmentDraft:
        if iteration_number >= 2:
            return DrawingAssessmentDraft(
                assessment=f'The mock drawing for “{intent}” has a clear focal structure.',
                decision="complete",
                reason="The deterministic mock completes after two observed passes.",
            )
        advice = self.propose_next_layer(
            intent=intent,
            iteration_number=iteration_number,
            drawable_width_mm=drawable_width_mm,
            drawable_height_mm=drawable_height_mm,
        )
        guidance_note = f" Guidance received: {guidance[-1]}" if guidance else ""
        return DrawingAssessmentDraft(
            assessment=f"{advice.interpretation}{guidance_note}",
            decision="continue",
            reason="One restrained additive pass will develop the composition.",
            svg_text=advice.svg_text,
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

    def plan_initial(
        self,
        *,
        intent: str,
        guidance: list[str],
        drawable_width_mm: float,
        drawable_height_mm: float,
    ) -> InitialDrawingPlanDraft:
        revisions = "\n".join(f"- {item}" for item in guidance[-10:]) or "- None"
        prompt = (
            f"Drawing intent: {intent}\n"
            f"Drawable SVG canvas: {drawable_width_mm} mm wide by "
            f"{drawable_height_mm} mm high.\n"
            f"Requested revisions:\n{revisions}\n\n"
            "Plan a physical pen drawing and provide only its first plotted layer. Describe a "
            "practical paper strategy and a subjective completion intent. The first layer must "
            "be useful on its own and leave room for later observed adjustments. The SVG root "
            "width and height must exactly match the drawable canvas in mm, its viewBox must "
            "start at 0 0 with those dimensions, and every mark must stay inside it. Use only "
            "svg, g, path, line, polyline, polygon, circle, ellipse, and rect elements, direct "
            "coordinates, fill=none, and black strokes. Do not include transforms or text."
        )
        parsed = self._request_structured(
            prompt=prompt,
            schema_name="initial_drawing_plan",
            schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "paper_strategy": {"type": "string"},
                    "completion_intent": {"type": "string"},
                    "svg": {"type": "string"},
                },
                "required": ["summary", "paper_strategy", "completion_intent", "svg"],
                "additionalProperties": False,
            },
        )
        values = [
            parsed.get("summary"),
            parsed.get("paper_strategy"),
            parsed.get("completion_intent"),
            parsed.get("svg"),
        ]
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ServiceUnavailableError("Drawing advisor returned an incomplete initial plan.")
        return InitialDrawingPlanDraft(
            summary=values[0].strip(),
            paper_strategy=values[1].strip(),
            completion_intent=values[2].strip(),
            svg_text=values[3].strip(),
        )

    def assess_iteration(
        self,
        *,
        intent: str,
        plan_summary: str,
        observed_image: bytes,
        observed_media_type: str,
        iteration_number: int,
        drawable_width_mm: float,
        drawable_height_mm: float,
        prior_interpretations: list[str],
        guidance: list[str],
    ) -> DrawingAssessmentDraft:
        history = "\n".join(f"- {item}" for item in prior_interpretations[-8:]) or "- None"
        queued = "\n".join(f"- {item}" for item in guidance) or "- None"
        prompt = (
            f"Drawing intent: {intent}\nPlan: {plan_summary}\n"
            f"Observed pass: {iteration_number}\n"
            f"Drawable SVG canvas: {drawable_width_mm} mm wide by "
            f"{drawable_height_mm} mm high.\n"
            f"Earlier assessments:\n{history}\nQueued guidance:\n{queued}\n\n"
            "Assess the registered photograph. Decide continue, complete, or pause. Continue "
            "only when another additive black-line layer materially improves the work. Complete "
            "when the intent reads and another pass risks overworking it. Pause when a person "
            "must change paper or correct a physical condition. For continue, return a safe "
            "incremental SVG on the exact canvas. Otherwise return null for svg."
        )
        parsed = self._request_structured(
            prompt=prompt,
            schema_name="drawing_assessment",
            schema={
                "type": "object",
                "properties": {
                    "assessment": {"type": "string"},
                    "decision": {"type": "string", "enum": ["continue", "complete", "pause"]},
                    "reason": {"type": "string"},
                    "svg": {"type": ["string", "null"]},
                    "requested_human_action": {"type": ["string", "null"]},
                },
                "required": [
                    "assessment",
                    "decision",
                    "reason",
                    "svg",
                    "requested_human_action",
                ],
                "additionalProperties": False,
            },
            image=(observed_image, observed_media_type),
        )
        assessment = parsed.get("assessment")
        decision = parsed.get("decision")
        reason = parsed.get("reason")
        svg_text = parsed.get("svg")
        action = parsed.get("requested_human_action")
        if (
            not isinstance(assessment, str)
            or decision not in {"continue", "complete", "pause"}
            or not isinstance(reason, str)
        ):
            raise ServiceUnavailableError("Drawing advisor returned an incomplete assessment.")
        if decision == "continue" and not isinstance(svg_text, str):
            raise ServiceUnavailableError("A continue decision must include an SVG layer.")
        return DrawingAssessmentDraft(
            assessment=assessment.strip(),
            decision=decision,
            reason=reason.strip(),
            svg_text=svg_text.strip() if isinstance(svg_text, str) else None,
            requested_human_action=action.strip() if isinstance(action, str) else None,
        )

    def _request_structured(
        self,
        *,
        prompt: str,
        schema_name: str,
        schema: dict,
        image: Optional[tuple[bytes, str]] = None,
    ) -> dict:
        if not self.status.available or not self._api_key or not self._model:
            raise ServiceUnavailableError(
                self.status.message or "OpenAI drawing advisor is not configured."
            )
        content = [{"type": "input_text", "text": prompt}]
        if image is not None:
            encoded_image = base64.b64encode(image[0]).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{image[1]};base64,{encoded_image}",
                    "detail": "high",
                }
            )
        payload = {
            "model": self._model,
            "store": False,
            "instructions": (
                "You are the creative planning and visual assessment component inside a local "
                "pen-plotter system. Return structured creative data only. You cannot control "
                "hardware or claim that a physical action occurred."
            ),
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
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
            return json.loads(_extract_output_text(response.json()))
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ServiceUnavailableError(f"Drawing advisor request failed: {exc}") from exc


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
