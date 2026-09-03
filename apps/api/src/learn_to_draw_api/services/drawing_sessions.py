from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from threading import RLock
from typing import Optional
import xml.etree.ElementTree as ET
from uuid import uuid4

from learn_to_draw_api.models import (
    AppConflictError,
    AppNotFoundError,
    DrawingIteration,
    DrawingIterationProposal,
    DrawingSession,
    DrawingSessionCreateRequest,
    InvalidArtifactError,
)
from learn_to_draw_api.services.drawing_advisor import DrawingAdvisor
from learn_to_draw_api.services.plot_workflow import PlotWorkflowService
from learn_to_draw_api.services.plot_workflow_preparation import (
    SVG_SHAPE_TAGS,
    extract_source_box,
    extract_source_content_ratios,
    parse_svg_root,
)
from learn_to_draw_api.services.plotter_workspace import PlotterWorkspaceService


ACTIVE_PLOT_RUN_STATUSES = {
    "pending",
    "plotting",
    "capturing",
    "awaiting_capture_review",
}
ALLOWED_ADVISOR_SVG_TAGS = SVG_SHAPE_TAGS | {"svg", "g", "title", "desc"}
DIMENSION_EPSILON_MM = 0.01


class DrawingSessionStore:
    def __init__(self, sessions_dir: Path) -> None:
        self._sessions_dir = sessions_dir
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, DrawingSession] = {}

    def save(self, session: DrawingSession) -> DrawingSession:
        path = self._sessions_dir / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        self._cache[session.id] = session
        return session

    def get(self, session_id: str) -> DrawingSession:
        cached = self._cache.get(session_id)
        if cached is not None:
            return cached
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            raise AppNotFoundError(f"Drawing session '{session_id}' was not found.")
        session = DrawingSession.model_validate_json(path.read_text(encoding="utf-8"))
        self._cache[session.id] = session
        return session

    def latest(self) -> Optional[DrawingSession]:
        sessions: list[DrawingSession] = []
        for path in self._sessions_dir.glob("*.json"):
            session = DrawingSession.model_validate_json(path.read_text(encoding="utf-8"))
            self._cache[session.id] = session
            sessions.append(session)
        sessions.sort(key=lambda item: item.created_at, reverse=True)
        return sessions[0] if sessions else None


class DrawingSessionService:
    def __init__(
        self,
        *,
        store: DrawingSessionStore,
        plot_workflow_service: PlotWorkflowService,
        workspace_service: PlotterWorkspaceService,
        advisor: DrawingAdvisor,
    ) -> None:
        self._store = store
        self._plot_workflow = plot_workflow_service
        self._workspace_service = workspace_service
        self._advisor = advisor
        self._lock = RLock()

    def create(self, request: DrawingSessionCreateRequest) -> DrawingSession:
        intent = request.intent.strip()
        if len(intent) < 3:
            raise InvalidArtifactError("Drawing intent must contain at least 3 characters.")
        with self._lock:
            asset = self._plot_workflow.get_asset(request.initial_asset_id)
            run = self._plot_workflow.create_run(asset.id)
            now = datetime.now(timezone.utc)
            session = DrawingSession(
                id=uuid4().hex,
                intent=intent,
                mode=request.mode,
                iteration_limit=request.iteration_limit,
                status="running",
                created_at=now,
                updated_at=now,
                iterations=[
                    DrawingIteration(
                        number=1,
                        asset=asset,
                        run_id=run.id,
                        created_at=now,
                    )
                ],
                advisor=self._advisor.status,
            )
            return self._store.save(session)

    def get(self, session_id: str) -> DrawingSession:
        with self._lock:
            return self._sync(self._store.get(session_id))

    def latest(self) -> Optional[DrawingSession]:
        with self._lock:
            session = self._store.latest()
            return self._sync(session) if session is not None else None

    def request_advice(self, session_id: str) -> DrawingSession:
        with self._lock:
            session = self._sync(self._store.get(session_id))
            if session.status != "observed":
                raise AppConflictError(
                    "Advice is available only after the current iteration has a registered observation."
                )
            if len(session.iterations) >= session.iteration_limit:
                raise AppConflictError("This drawing session has reached its iteration limit.")
            current_iteration = session.iterations[-1]
            run = self._plot_workflow.get_run(current_iteration.run_id)
            capture = run.observed_result.capture if run.observed_result else run.capture
            if (
                capture is None
                or capture.normalized is None
                or capture.review is None
                or capture.review.review_status != "confirmed"
            ):
                raise AppConflictError(
                    "The current iteration does not have a registered observed result."
                )
            image_path = Path(capture.file_path).with_name(
                f"{capture.id}-rectified-grayscale.png"
            )
            if not image_path.exists():
                raise AppConflictError("The registered observed image is unavailable.")
            workspace = self._workspace_service.current_validated()
            plot_area = workspace.to_plot_area()
            prior_interpretations = [
                iteration.next_proposal.interpretation
                for iteration in session.iterations
                if iteration.next_proposal is not None
            ]
            advice = self._advisor.propose_next_layer(
                intent=session.intent,
                observed_image=image_path.read_bytes(),
                observed_media_type="image/png",
                iteration_number=current_iteration.number,
                iteration_limit=session.iteration_limit,
                drawable_width_mm=plot_area.draw_width_mm,
                drawable_height_mm=plot_area.draw_height_mm,
                prior_interpretations=prior_interpretations,
            )
            if not advice.interpretation.strip():
                raise InvalidArtifactError("Drawing advisor returned an empty interpretation.")
            safe_svg = validate_and_normalize_advisor_svg(
                advice.svg_text,
                drawable_width_mm=plot_area.draw_width_mm,
                drawable_height_mm=plot_area.draw_height_mm,
            )
            next_number = current_iteration.number + 1
            asset = self._plot_workflow.create_generated_asset(
                name=f"{session.intent[:48]} — pass {next_number}",
                svg_text=safe_svg,
            )
            current_iteration.next_proposal = DrawingIterationProposal(
                interpretation=advice.interpretation.strip(),
                asset=asset,
                advisor_driver=self._advisor.status.driver,
                advisor_model=self._advisor.status.model,
                created_at=datetime.now(timezone.utc),
            )
            session.status = "proposal_ready"
            session.advisor = self._advisor.status
            session.error = None
            session.updated_at = datetime.now(timezone.utc)
            return self._store.save(session)

    def approve_next_iteration(self, session_id: str) -> DrawingSession:
        with self._lock:
            session = self._sync(self._store.get(session_id))
            if session.status != "proposal_ready":
                raise AppConflictError("This drawing session has no proposal ready to plot.")
            current_iteration = session.iterations[-1]
            proposal = current_iteration.next_proposal
            if proposal is None or proposal.approved_run_id is not None:
                raise AppConflictError("This drawing proposal has already been used.")
            if len(session.iterations) >= session.iteration_limit:
                raise AppConflictError("This drawing session has reached its iteration limit.")
            run = self._plot_workflow.create_run(proposal.asset.id)
            now = datetime.now(timezone.utc)
            proposal.approved_at = now
            proposal.approved_run_id = run.id
            session.iterations.append(
                DrawingIteration(
                    number=current_iteration.number + 1,
                    asset=proposal.asset,
                    run_id=run.id,
                    created_at=now,
                )
            )
            session.status = "running"
            session.updated_at = now
            session.error = None
            return self._store.save(session)

    def _sync(self, session: DrawingSession) -> DrawingSession:
        current_iteration = session.iterations[-1]
        run = self._plot_workflow.get_run(current_iteration.run_id)
        previous_status = session.status
        if run.status == "awaiting_capture_review":
            session.status = "awaiting_capture_review"
        elif run.status in ACTIVE_PLOT_RUN_STATUSES:
            session.status = "running"
        elif run.status == "failed":
            session.status = "failed"
            session.error = run.error
        elif len(session.iterations) >= session.iteration_limit:
            session.status = "completed"
            session.error = None
        elif (
            current_iteration.next_proposal is not None
            and current_iteration.next_proposal.approved_run_id is None
        ):
            session.status = "proposal_ready"
            session.error = None
        else:
            session.status = "observed"
            session.error = None
        session.advisor = self._advisor.status
        if session.status != previous_status:
            session.updated_at = datetime.now(timezone.utc)
            self._store.save(session)
        return session


def validate_and_normalize_advisor_svg(
    svg_text: str,
    *,
    drawable_width_mm: float,
    drawable_height_mm: float,
) -> str:
    root = parse_svg_root(svg_text)
    source_box = extract_source_box(root)
    dimensions = (
        source_box.physical_width_mm,
        source_box.physical_height_mm,
        source_box.view_box_min_x,
        source_box.view_box_min_y,
        source_box.view_box_width,
        source_box.view_box_height,
    )
    if not all(value is not None and math.isfinite(value) for value in dimensions):
        raise InvalidArtifactError(
            "Advisor SVG must declare finite physical dimensions and a viewBox."
        )
    if (
        abs((source_box.physical_width_mm or 0) - drawable_width_mm)
        > DIMENSION_EPSILON_MM
        or abs((source_box.physical_height_mm or 0) - drawable_height_mm)
        > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_min_x) > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_min_y) > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_width - drawable_width_mm) > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_height - drawable_height_mm) > DIMENSION_EPSILON_MM
    ):
        raise InvalidArtifactError(
            "Advisor SVG canvas must exactly match the current drawable area in millimeters."
        )
    shape_count = 0
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in ALLOWED_ADVISOR_SVG_TAGS:
            raise InvalidArtifactError(f"Advisor SVG element '{tag}' is not allowed.")
        for attribute in element.attrib:
            local_attribute = attribute.rsplit("}", 1)[-1].lower()
            if local_attribute.startswith("on") or local_attribute in {
                "href",
                "style",
                "class",
                "transform",
            }:
                raise InvalidArtifactError(
                    f"Advisor SVG attribute '{local_attribute}' is not allowed."
                )
        if tag in SVG_SHAPE_TAGS:
            shape_count += 1
            element.attrib["fill"] = "none"
            element.attrib["stroke"] = "black"
            element.attrib["stroke-width"] = "0.6"
    if shape_count == 0:
        raise InvalidArtifactError("Advisor SVG must contain at least one drawable mark.")
    content_ratios = extract_source_content_ratios(root, source_box=source_box)
    if content_ratios is None:
        raise InvalidArtifactError("Advisor SVG marks could not be bounded safely.")
    left, top, width, height = content_ratios
    if (
        left < -DIMENSION_EPSILON_MM
        or top < -DIMENSION_EPSILON_MM
        or left + width > 1 + DIMENSION_EPSILON_MM
        or top + height > 1 + DIMENSION_EPSILON_MM
    ):
        raise InvalidArtifactError("Advisor SVG contains marks outside the drawable area.")
    return ET.tostring(root, encoding="unicode")
