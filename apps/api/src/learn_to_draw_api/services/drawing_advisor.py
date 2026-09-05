from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass, field
import json
from threading import RLock
from typing import Literal, Optional

import httpx

from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    AppConflictError,
    DrawingAdvisorRuntimeStatus,
    DrawingAdvisorStatus,
    InvalidArtifactError,
    ServiceUnavailableError,
)
from learn_to_draw_api.services.advisor_svg import (
    render_advisor_svg_png,
    validate_and_normalize_advisor_svg,
)


OPENAI_REQUEST_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class DrawingAdviceDraft:
    interpretation: str
    svg_text: str


@dataclass(frozen=True)
class CreativeCriterionAssessmentDraft:
    rank: int
    criterion: str
    outcome: Literal["meets", "partially_meets", "misses"]
    assessment: str


@dataclass(frozen=True)
class CandidateQualityReviewDraft:
    summary: str
    decision: Literal["accept", "revise"]
    revision_applied: bool
    criterion_assessments: list[CreativeCriterionAssessmentDraft]


@dataclass(frozen=True)
class _CandidateReviewResponse:
    summary: str
    decision: Literal["accept", "revise"]
    criterion_assessments: list[CreativeCriterionAssessmentDraft]
    svg_text: Optional[str]


@dataclass(frozen=True)
class InitialDrawingPlanDraft:
    summary: str
    paper_strategy: str
    completion_intent: str
    creative_criteria: list[str]
    quality_review: CandidateQualityReviewDraft
    svg_text: str


@dataclass(frozen=True)
class DrawingAssessmentDraft:
    assessment: str
    decision: Literal["continue", "complete", "pause"]
    reason: str
    svg_text: Optional[str] = None
    requested_human_action: Optional[str] = None
    criterion_assessments: list[CreativeCriterionAssessmentDraft] = field(
        default_factory=list
    )


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
        creative_criteria: list[str],
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


class RuntimeDrawingAdvisor(DrawingAdvisor):
    """Thread-safe advisor delegate with an optional process-memory override."""

    def __init__(self, startup_advisor: DrawingAdvisor) -> None:
        self._startup_advisor = startup_advisor
        self._active_advisor = startup_advisor
        self._source: Literal["startup", "runtime"] = "startup"
        self._lock = RLock()

    @property
    def status(self) -> DrawingAdvisorStatus:
        return self._snapshot().status

    @property
    def runtime_status(self) -> DrawingAdvisorRuntimeStatus:
        with self._lock:
            advisor = self._active_advisor
            source = self._source
        return DrawingAdvisorRuntimeStatus(advisor=advisor.status, source=source)

    def configure_openai(self, *, api_key: str, model: str) -> DrawingAdvisorRuntimeStatus:
        normalized_key = api_key.strip()
        normalized_model = model.strip()
        if not normalized_key:
            raise InvalidArtifactError("Enter an OpenAI API key.")
        if len(normalized_key) > 4096:
            raise InvalidArtifactError("The OpenAI API key is too long.")
        if not normalized_model:
            raise InvalidArtifactError("Enter an OpenAI model.")

        candidate = OpenAIDrawingAdvisor(
            api_key=normalized_key,
            model=normalized_model,
        )
        with self._lock:
            self._active_advisor = candidate
            self._source = "runtime"
        return self.runtime_status

    def update_openai_model(self, *, model: str) -> DrawingAdvisorRuntimeStatus:
        normalized_model = model.strip()
        if not normalized_model:
            raise InvalidArtifactError("Enter an OpenAI model.")
        with self._lock:
            active_advisor = self._active_advisor
            if (
                not isinstance(active_advisor, OpenAIDrawingAdvisor)
                or not active_advisor.has_api_key
            ):
                raise AppConflictError(
                    "Configure an OpenAI API key before changing the model."
                )
            self._active_advisor = active_advisor.with_model(normalized_model)
            self._source = "runtime"
        return self.runtime_status

    def clear_runtime_configuration(self) -> DrawingAdvisorRuntimeStatus:
        with self._lock:
            self._active_advisor = self._startup_advisor
            self._source = "startup"
        return self.runtime_status

    def plan_initial(self, **kwargs) -> InitialDrawingPlanDraft:
        return self._snapshot().plan_initial(**kwargs)

    def assess_iteration(self, **kwargs) -> DrawingAssessmentDraft:
        return self._snapshot().assess_iteration(**kwargs)

    def propose_next_layer(self, **kwargs) -> DrawingAdviceDraft:
        return self._snapshot().propose_next_layer(**kwargs)

    def _snapshot(self) -> DrawingAdvisor:
        with self._lock:
            return self._active_advisor


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
        creative_criteria = [
            f'Express the distinctive character of “{intent}”.',
            "Use intentional, lively pen marks rather than generic diagram geometry.",
            "Keep a clear composition with enough open paper for later passes.",
        ]
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
            creative_criteria=creative_criteria,
            quality_review=CandidateQualityReviewDraft(
                summary="The deterministic mock candidate meets its creative test criteria.",
                decision="accept",
                revision_applied=False,
                criterion_assessments=[
                    CreativeCriterionAssessmentDraft(
                        rank=index,
                        criterion=criterion,
                        outcome="meets",
                        assessment="The mock candidate intentionally satisfies this criterion.",
                    )
                    for index, criterion in enumerate(creative_criteria, start=1)
                ],
            ),
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
        creative_criteria: list[str],
        **_kwargs,
    ) -> DrawingAssessmentDraft:
        criteria = creative_criteria or [f'Fulfill the drawing intent: “{intent}”.']
        criterion_assessments = [
            CreativeCriterionAssessmentDraft(
                rank=index,
                criterion=criterion,
                outcome="meets" if iteration_number >= 2 else "partially_meets",
                assessment=(
                    "The mock observation satisfies this criterion."
                    if iteration_number >= 2
                    else "The mock observation can develop this criterion with one more pass."
                ),
            )
            for index, criterion in enumerate(criteria, start=1)
        ]
        if iteration_number >= 2:
            return DrawingAssessmentDraft(
                assessment=f'The mock drawing for “{intent}” has a clear focal structure.',
                decision="complete",
                reason="The deterministic mock completes after two observed passes.",
                criterion_assessments=criterion_assessments,
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
            criterion_assessments=criterion_assessments,
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

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def with_model(self, model: str) -> OpenAIDrawingAdvisor:
        return OpenAIDrawingAdvisor(api_key=self._api_key, model=model)

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
                timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            response_payload = response.json()
            output_text = _extract_output_text(response_payload)
            parsed = json.loads(output_text)
        except httpx.TimeoutException as exc:
            raise ServiceUnavailableError(self._timeout_message()) from exc
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
            "Plan a physical pen drawing and provide only its first plotted layer. First return "
            "three to five ordered creative criteria. Rank the qualities that make this request "
            "distinctive first: medium, technique, mood, scientific or expressive character, "
            "and composition should outrank generic subject recognition unless the person says "
            "otherwise. Do not list SVG safety or simple recognizability as a creative success "
            "criterion. Describe a practical paper strategy and a subjective completion intent. "
            "Every mark in the SVG will become permanent ink. Do not include disposable axes, "
            "baselines, boxes, or construction guides unless they are visibly part of the "
            "requested finished style. The first layer must strongly express the highest-ranked "
            "criteria, be useful on its own, and leave room for later observed adjustments. The "
            "SVG root width and height must exactly match the drawable canvas in mm, its viewBox "
            "must start at 0 0 with those dimensions, and every mark must stay inside it. Use "
            "only svg, g, path, line, polyline, polygon, circle, ellipse, and rect elements, "
            "direct coordinates, fill=none, and black strokes. Do not include transforms or text."
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
                    "creative_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 5,
                    },
                    "svg": {"type": "string"},
                },
                "required": [
                    "summary",
                    "paper_strategy",
                    "completion_intent",
                    "creative_criteria",
                    "svg",
                ],
                "additionalProperties": False,
            },
        )
        summary = parsed.get("summary")
        paper_strategy = parsed.get("paper_strategy")
        completion_intent = parsed.get("completion_intent")
        candidate_svg = parsed.get("svg")
        if not all(
            isinstance(value, str) and value.strip()
            for value in [summary, paper_strategy, completion_intent, candidate_svg]
        ):
            raise ServiceUnavailableError("Drawing advisor returned an incomplete initial plan.")
        creative_criteria = _parse_creative_criteria(parsed.get("creative_criteria"))
        safe_candidate = validate_and_normalize_advisor_svg(
            candidate_svg,
            drawable_width_mm=drawable_width_mm,
            drawable_height_mm=drawable_height_mm,
        )
        candidate_png = render_advisor_svg_png(
            safe_candidate,
            drawable_width_mm=drawable_width_mm,
            drawable_height_mm=drawable_height_mm,
        )
        review = self._review_initial_candidate(
            intent=intent,
            plan_summary=summary.strip(),
            creative_criteria=creative_criteria,
            candidate_png=candidate_png,
            drawable_width_mm=drawable_width_mm,
            drawable_height_mm=drawable_height_mm,
        )
        final_svg = safe_candidate
        if review.decision == "revise":
            if not review.svg_text:
                raise ServiceUnavailableError(
                    "Creative review requested a revision without a replacement SVG."
                )
            final_svg = validate_and_normalize_advisor_svg(
                review.svg_text,
                drawable_width_mm=drawable_width_mm,
                drawable_height_mm=drawable_height_mm,
            )
        return InitialDrawingPlanDraft(
            summary=summary.strip(),
            paper_strategy=paper_strategy.strip(),
            completion_intent=completion_intent.strip(),
            creative_criteria=creative_criteria,
            quality_review=CandidateQualityReviewDraft(
                summary=review.summary,
                decision=review.decision,
                revision_applied=review.decision == "revise",
                criterion_assessments=review.criterion_assessments,
            ),
            svg_text=final_svg,
        )

    def _review_initial_candidate(
        self,
        *,
        intent: str,
        plan_summary: str,
        creative_criteria: list[str],
        candidate_png: bytes,
        drawable_width_mm: float,
        drawable_height_mm: float,
    ) -> _CandidateReviewResponse:
        criteria_text = "\n".join(
            f"{index}. {criterion}"
            for index, criterion in enumerate(creative_criteria, start=1)
        )
        prompt = (
            f"Drawing intent: {intent}\nPlan: {plan_summary}\n"
            f"Drawable SVG canvas: {drawable_width_mm} mm wide by "
            f"{drawable_height_mm} mm high.\n"
            f"Ranked creative criteria:\n{criteria_text}\n\n"
            "The image is an exact black-on-white raster of the normalized first-pass SVG that "
            "would be plotted. Review the visible candidate, not the plan's claims. Return exactly "
            "one finding for each criterion using its rank. Treat the criteria in order: a merely "
            "recognizable subject does not compensate for missing the requested medium, technique, "
            "mood, scientific character, or other higher-ranked quality. Remember that every line "
            "is permanent ink and that later passes can add but cannot erase. Accept only if this "
            "is a sound irreversible foundation. Otherwise choose revise and return one complete "
            "replacement first-pass SVG, not an additive patch. The replacement must address the "
            "findings and self-check against every criterion before returning. Its root dimensions "
            "and viewBox must match the canvas exactly; use only svg, g, path, line, polyline, "
            "polygon, circle, ellipse, and rect with direct coordinates, fill=none, black strokes, "
            "no transforms, and no text. For accept, return null for svg."
        )
        parsed = self._request_structured(
            prompt=prompt,
            schema_name="initial_candidate_review",
            schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "decision": {"type": "string", "enum": ["accept", "revise"]},
                    "criterion_assessments": {
                        "type": "array",
                        "items": _criterion_assessment_schema(),
                        "minItems": 3,
                        "maxItems": 5,
                    },
                    "svg": {"type": ["string", "null"]},
                },
                "required": ["summary", "decision", "criterion_assessments", "svg"],
                "additionalProperties": False,
            },
            image=(candidate_png, "image/png"),
        )
        summary = parsed.get("summary")
        decision = parsed.get("decision")
        svg_text = parsed.get("svg")
        if (
            not isinstance(summary, str)
            or not summary.strip()
            or decision not in {"accept", "revise"}
        ):
            raise ServiceUnavailableError("Drawing advisor returned an incomplete creative review.")
        if decision == "accept" and svg_text is not None:
            raise ServiceUnavailableError(
                "An accepted creative review must not include a replacement SVG."
            )
        if decision == "revise" and not (
            isinstance(svg_text, str) and svg_text.strip()
        ):
            raise ServiceUnavailableError(
                "Creative review requested a revision without a replacement SVG."
            )
        return _CandidateReviewResponse(
            summary=summary.strip(),
            decision=decision,
            criterion_assessments=_parse_criterion_assessments(
                parsed.get("criterion_assessments"),
                creative_criteria,
            ),
            svg_text=svg_text.strip() if isinstance(svg_text, str) else None,
        )

    def assess_iteration(
        self,
        *,
        intent: str,
        plan_summary: str,
        creative_criteria: list[str],
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
        criteria = creative_criteria or [f"Fulfill the drawing intent: {intent}"]
        criteria_text = "\n".join(
            f"{index}. {criterion}" for index, criterion in enumerate(criteria, start=1)
        )
        prompt = (
            f"Drawing intent: {intent}\nPlan: {plan_summary}\n"
            f"Observed pass: {iteration_number}\n"
            f"Drawable SVG canvas: {drawable_width_mm} mm wide by "
            f"{drawable_height_mm} mm high.\n"
            f"Ranked creative criteria:\n{criteria_text}\n"
            f"Earlier assessments:\n{history}\nQueued guidance:\n{queued}\n\n"
            "Assess the registered photograph against every criterion in rank order and return "
            "exactly one finding for each rank. Judge the visible drawing rather than reinforcing "
            "earlier assessments. A recognizable subject does not compensate for missing a "
            "higher-ranked stylistic, technical, scientific, or expressive objective. Decide "
            "continue, complete, or pause. Continue only when a specific additive black-line layer "
            "can materially close a named criterion gap. Complete when the highest-ranked criteria "
            "are satisfied and another pass risks overworking the page. If the foundation is wrong "
            "and cannot be repaired additively, pause and request a new-sheet or replanning action; "
            "do not add detail that merely reinforces the wrong direction. Also pause when a person "
            "must correct a physical condition. For continue, return a safe incremental SVG on the "
            "exact canvas. Otherwise return null for svg."
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
                    "criterion_assessments": {
                        "type": "array",
                        "items": _criterion_assessment_schema(),
                        "minItems": 1,
                        "maxItems": 5,
                    },
                    "svg": {"type": ["string", "null"]},
                    "requested_human_action": {"type": ["string", "null"]},
                },
                "required": [
                    "assessment",
                    "decision",
                    "reason",
                    "criterion_assessments",
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
            criterion_assessments=_parse_criterion_assessments(
                parsed.get("criterion_assessments"),
                criteria,
            ),
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
                timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return json.loads(_extract_output_text(response.json()))
        except httpx.TimeoutException as exc:
            raise ServiceUnavailableError(self._timeout_message()) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ServiceUnavailableError(f"Drawing advisor request failed: {exc}") from exc

    @staticmethod
    def _timeout_message() -> str:
        return (
            "Drawing advisor request timed out after "
            f"{OPENAI_REQUEST_TIMEOUT_SECONDS} seconds. Retry the session, or choose a "
            "faster model in Controls."
        )


def _criterion_assessment_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "rank": {"type": "integer"},
            "outcome": {
                "type": "string",
                "enum": ["meets", "partially_meets", "misses"],
            },
            "assessment": {"type": "string"},
        },
        "required": ["rank", "outcome", "assessment"],
        "additionalProperties": False,
    }


def _parse_creative_criteria(value) -> list[str]:
    if not isinstance(value, list) or not 3 <= len(value) <= 5:
        raise ServiceUnavailableError(
            "Drawing advisor must return three to five ranked creative criteria."
        )
    criteria = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ServiceUnavailableError(
                "Drawing advisor returned an invalid creative criterion."
            )
        criteria.append(item.strip())
    if len({criterion.casefold() for criterion in criteria}) != len(criteria):
        raise ServiceUnavailableError(
            "Drawing advisor returned duplicate creative criteria."
        )
    return criteria


def _parse_criterion_assessments(
    value,
    criteria: list[str],
) -> list[CreativeCriterionAssessmentDraft]:
    if not isinstance(value, list) or len(value) != len(criteria):
        raise ServiceUnavailableError(
            "Drawing advisor must assess every ranked creative criterion exactly once."
        )
    by_rank = {}
    for item in value:
        if not isinstance(item, dict):
            raise ServiceUnavailableError(
                "Drawing advisor returned an invalid creative criterion assessment."
            )
        rank = item.get("rank")
        outcome = item.get("outcome")
        assessment = item.get("assessment")
        if (
            not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank < 1
            or rank > len(criteria)
            or rank in by_rank
            or outcome not in {"meets", "partially_meets", "misses"}
            or not isinstance(assessment, str)
            or not assessment.strip()
        ):
            raise ServiceUnavailableError(
                "Drawing advisor returned an invalid creative criterion assessment."
            )
        by_rank[rank] = CreativeCriterionAssessmentDraft(
            rank=rank,
            criterion=criteria[rank - 1],
            outcome=outcome,
            assessment=assessment.strip(),
        )
    if set(by_rank) != set(range(1, len(criteria) + 1)):
        raise ServiceUnavailableError(
            "Drawing advisor must assess every ranked creative criterion exactly once."
        )
    return [by_rank[rank] for rank in range(1, len(criteria) + 1)]


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
