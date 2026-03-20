from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Optional

from learn_to_draw_api.models import AppNotFoundError, PlotRun, PlotRunListResponse, PlotRunSummary


ACTIVE_RUN_STATUSES = {"pending", "plotting", "capturing"}


class PlotRunStore:
    def __init__(self, runs_dir: Path) -> None:
        self._runs_dir = runs_dir
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PlotRun] = {}
        self._lock = Lock()

    def save(self, run: PlotRun) -> PlotRun:
        with self._lock:
            metadata_path = self._runs_dir / f"{run.id}.json"
            metadata_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
            self._cache[run.id] = run
        return run

    def save_prepared_svg(self, run_id: str, svg_text: str) -> Path:
        with self._lock:
            prepared_path = self._runs_dir / f"{run_id}-prepared.svg"
            prepared_path.write_text(svg_text, encoding="utf-8")
        return prepared_path

    def get(self, run_id: str) -> PlotRun:
        cached = self._cache.get(run_id)
        if cached is not None:
            return cached
        metadata_path = self._runs_dir / f"{run_id}.json"
        if not metadata_path.exists():
            raise AppNotFoundError(f"Plot run '{run_id}' was not found.")
        run = PlotRun.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        self._cache[run_id] = run
        return run

    def latest(self) -> Optional[PlotRun]:
        runs = self.list_full_runs()
        return runs[0] if runs else None

    def list_full_runs(self) -> list[PlotRun]:
        runs: list[PlotRun] = []
        for metadata_path in self._runs_dir.glob("*.json"):
            run = PlotRun.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            self._cache[run.id] = run
            runs.append(run)
        runs.sort(key=lambda run: run.created_at, reverse=True)
        return runs

    def list_summaries(self) -> PlotRunListResponse:
        return PlotRunListResponse(
            runs=[PlotRunSummary.from_run(run) for run in self.list_full_runs()]
        )
