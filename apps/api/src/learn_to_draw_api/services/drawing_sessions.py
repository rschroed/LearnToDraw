from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from threading import RLock, Thread
from typing import Optional
import xml.etree.ElementTree as ET
from uuid import uuid4

from learn_to_draw_api.models import (
    AppConflictError,
    AppNotFoundError,
    DrawingIteration,
    DrawingIterationProposal,
    DrawingSessionAuthorization,
    DrawingSessionEvent,
    DrawingSessionListResponse,
    DrawingSessionMessageRequest,
    DrawingSessionPlan,
    DrawingSessionProposal,
    DrawingSessionSummary,
    DrawingSession,
    DrawingSessionCreateRequest,
    InvalidArtifactError,
    ServiceUnavailableError,
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
        sessions = self.list()
        return sessions[0] if sessions else None

    def list(self) -> list[DrawingSession]:
        sessions: list[DrawingSession] = []
        for path in self._sessions_dir.glob("*.json"):
            session = DrawingSession.model_validate_json(path.read_text(encoding="utf-8"))
            self._cache[session.id] = session
            sessions.append(session)
        sessions.sort(key=lambda item: item.created_at, reverse=True)
        return sessions


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
        if request.initial_asset_id is None:
            return self._create_v2(intent)
        with self._lock:
            asset = self._plot_workflow.get_asset(request.initial_asset_id)
            run = self._plot_workflow.create_run(asset.id)
            now = datetime.now(timezone.utc)
            session = DrawingSession(
                id=uuid4().hex,
                session_version=1,
                intent=intent,
                mode=request.mode,
                iteration_limit=request.iteration_limit or 3,
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
                pass_count=1,
                current_run_id=run.id,
            )
            return self._store.save(session)

    def _create_v2(self, intent: str) -> DrawingSession:
        with self._lock:
            now = datetime.now(timezone.utc)
            session = DrawingSession(
                id=uuid4().hex,
                session_version=2,
                intent=intent,
                status="planning",
                created_at=now,
                updated_at=now,
                advisor=self._advisor.status,
                planning_generation=1,
                authorization=DrawingSessionAuthorization(),
                events=[
                    self._event(
                        "session_created",
                        "Creative session created. Planning the first pass.",
                    )
                ],
            )
            self._store.save(session)
            self._dispatch_plan(session.id, session.planning_generation)
            return session

    def get(self, session_id: str) -> DrawingSession:
        with self._lock:
            return self._sync(self._store.get(session_id))

    def latest(self) -> Optional[DrawingSession]:
        with self._lock:
            session = self._store.latest()
            return self._sync(session) if session is not None else None

    def list(self) -> DrawingSessionListResponse:
        with self._lock:
            summaries = []
            for stored in self._store.list():
                session = self._sync(stored)
                preview_url = None
                if session.current_proposal is not None:
                    preview_url = session.current_proposal.asset.public_url
                elif session.iterations:
                    preview_url = session.iterations[-1].asset.public_url
                summaries.append(
                    DrawingSessionSummary(
                        id=session.id,
                        session_version=session.session_version,
                        intent=session.intent,
                        status=session.status,
                        pass_count=(
                            session.pass_count
                            if session.session_version == 2
                            else len(session.iterations)
                        ),
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                        preview_url=preview_url,
                    )
                )
            return DrawingSessionListResponse(sessions=summaries)

    def add_message(
        self,
        session_id: str,
        request: DrawingSessionMessageRequest,
    ) -> DrawingSession:
        message = request.text.strip()
        if not message:
            raise InvalidArtifactError("Guidance must not be empty.")
        with self._lock:
            session = self._sync(self._store.get(session_id))
            if session.session_version != 2:
                raise AppConflictError("Messages are available only for V2 drawing sessions.")
            if session.status in {"completed", "failed", "stopping"}:
                raise AppConflictError("This drawing session is not accepting guidance.")
            session.queued_guidance.append(message)
            session.events.append(self._event("user_guidance", message))
            session.updated_at = datetime.now(timezone.utc)
            if session.authorization.approved_at is None:
                session.status = "planning"
                session.error = None
                session.plan = None
                session.current_proposal = None
                session.planning_generation += 1
                generation = session.planning_generation
                self._store.save(session)
                self._dispatch_plan(session.id, generation)
            else:
                self._store.save(session)
            return session

    def approve(self, session_id: str) -> DrawingSession:
        with self._lock:
            session = self._sync(self._store.get(session_id))
            if session.session_version != 2:
                raise AppConflictError("Use the legacy iteration endpoint for V1 sessions.")
            if session.status != "awaiting_approval" or session.current_proposal is None:
                raise AppConflictError("This drawing session has no first pass ready to approve.")
            if session.authorization.approved_at is not None:
                raise AppConflictError("This drawing session has already been approved.")
            asset = self._plot_workflow.get_asset(session.current_proposal.asset.id)
            run = self._plot_workflow.create_run(asset.id)
            now = datetime.now(timezone.utc)
            session.authorization.approved_at = now
            session.authorization.stop_requested = False
            session.approved_at = now
            session.current_run_id = run.id
            session.pass_count = 1
            session.iterations.append(
                DrawingIteration(
                    number=1,
                    asset=asset,
                    run_id=run.id,
                    created_at=now,
                )
            )
            session.events.extend(
                [
                    self._event(
                        "session_approved",
                        "Open-ended attended drawing session approved.",
                    ),
                    self._event(
                        "plot_started",
                        "Started the approved first pass.",
                        asset_id=asset.id,
                        run_id=run.id,
                    ),
                ]
            )
            session.status = "running"
            session.updated_at = now
            session.error = None
            return self._store.save(session)

    def request_advice(self, session_id: str) -> DrawingSession:
        with self._lock:
            session = self._sync(self._store.get(session_id))
            if session.session_version != 1:
                raise AppConflictError("Advice is coordinated automatically for V2 sessions.")
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
            if session.session_version != 1:
                raise AppConflictError("Use session approval for V2 drawing sessions.")
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
        if session.session_version == 2:
            return self._sync_v2(session)
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

    def _sync_v2(self, session: DrawingSession) -> DrawingSession:
        if session.current_run_id is None:
            session.advisor = self._advisor.status
            return session
        run = self._plot_workflow.get_run(session.current_run_id)
        previous_status = session.status
        if run.status == "awaiting_capture_review":
            session.status = "awaiting_capture_review"
        elif run.status in ACTIVE_PLOT_RUN_STATUSES:
            session.status = "running"
        elif run.status == "failed":
            session.status = "failed"
            session.error = run.error
        elif session.status not in {"completed", "failed"}:
            session.status = "paused"
            session.paused_at = datetime.now(timezone.utc)
            session.error = None
            if previous_status != "paused":
                session.events.append(
                    self._event(
                        "observation_ready",
                        "The registered first-pass observation is ready.",
                        run_id=run.id,
                    )
                )
                session.events.append(
                    self._event(
                        "session_paused",
                        "Automatic continuation is not enabled in this contract slice.",
                        run_id=run.id,
                    )
                )
        session.advisor = self._advisor.status
        if session.status != previous_status:
            session.updated_at = datetime.now(timezone.utc)
            self._store.save(session)
        return session

    def _dispatch_plan(self, session_id: str, generation: int) -> None:
        Thread(
            target=self._plan_session,
            args=(session_id, generation),
            daemon=True,
            name=f"drawing-plan-{session_id[:8]}",
        ).start()

    def _plan_session(self, session_id: str, generation: int) -> None:
        try:
            with self._lock:
                session = self._store.get(session_id)
                if session.session_version != 2 or session.planning_generation != generation:
                    return
                intent = session.intent
                guidance = list(session.queued_guidance)
                workspace = self._workspace_service.current_validated()
                plot_area = workspace.to_plot_area()
            draft = self._advisor.plan_initial(
                intent=intent,
                guidance=guidance,
                drawable_width_mm=plot_area.draw_width_mm,
                drawable_height_mm=plot_area.draw_height_mm,
            )
            safe_svg = validate_and_normalize_advisor_svg(
                draft.svg_text,
                drawable_width_mm=plot_area.draw_width_mm,
                drawable_height_mm=plot_area.draw_height_mm,
            )
            asset = self._plot_workflow.create_generated_asset(
                name=f"{intent[:48]} — first pass",
                svg_text=safe_svg,
            )
            with self._lock:
                session = self._store.get(session_id)
                if session.planning_generation != generation or session.status != "planning":
                    return
                now = datetime.now(timezone.utc)
                session.plan = DrawingSessionPlan(
                    summary=draft.summary.strip(),
                    paper_strategy=draft.paper_strategy.strip(),
                    completion_intent=draft.completion_intent.strip(),
                )
                session.current_proposal = DrawingSessionProposal(
                    asset=asset,
                    created_at=now,
                    advisor_driver=self._advisor.status.driver,
                    advisor_model=self._advisor.status.model,
                )
                session.status = "awaiting_approval"
                session.error = None
                session.advisor = self._advisor.status
                session.updated_at = now
                session.events.append(
                    self._event(
                        "plan_ready",
                        "The drawing plan and first-pass preview are ready.",
                        asset_id=asset.id,
                        details={
                            "summary": session.plan.summary,
                            "paper_strategy": session.plan.paper_strategy,
                            "completion_intent": session.plan.completion_intent,
                        },
                    )
                )
                self._store.save(session)
        except (InvalidArtifactError, ServiceUnavailableError, AppConflictError) as exc:
            with self._lock:
                session = self._store.get(session_id)
                if session.planning_generation != generation:
                    return
                now = datetime.now(timezone.utc)
                session.status = "paused"
                session.paused_at = now
                session.error = str(exc)
                session.advisor = self._advisor.status
                session.updated_at = now
                session.events.append(self._event("plan_failed", str(exc)))
                self._store.save(session)

    @staticmethod
    def _event(
        event_type,
        message: str,
        *,
        asset_id: Optional[str] = None,
        run_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> DrawingSessionEvent:
        return DrawingSessionEvent(
            id=uuid4().hex,
            type=event_type,
            created_at=datetime.now(timezone.utc),
            message=message,
            asset_id=asset_id,
            run_id=run_id,
            details=details or {},
        )


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
