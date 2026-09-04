from __future__ import annotations

from dataclasses import asdict
import multiprocessing
import os
import queue
import signal
from threading import Lock
from typing import Callable

from learn_to_draw_api.adapters.axidraw_client import (
    AxiDrawPlotExecution,
    PyAxiDrawClient,
    PyAxiDrawClientError,
)


class AxiDrawProcessPlotRunner:
    """Runs Plot context in its own signal-owning process."""

    def __init__(
        self,
        *,
        settings_provider: Callable[[], dict],
        context=None,
        signal_sender: Callable[[int, int], None] = os.kill,
    ) -> None:
        self._settings_provider = settings_provider
        self._context = context or multiprocessing.get_context("spawn")
        self._signal_sender = signal_sender
        self._lock = Lock()
        self._active_process = None
        self._stop_requested = False

    def run(self, svg_text: str) -> AxiDrawPlotExecution:
        result_queue = self._context.Queue(maxsize=1)
        process = self._context.Process(
            target=_run_plot_worker,
            args=(self._settings_provider(), svg_text, result_queue),
            daemon=True,
        )
        with self._lock:
            if self._active_process is not None and self._active_process.is_alive():
                raise PyAxiDrawClientError("An AxiDraw plot worker is already active.")
            self._active_process = process
            self._stop_requested = False
            process.start()
        try:
            payload = None
            while payload is None:
                try:
                    payload = result_queue.get(timeout=0.1)
                except queue.Empty:
                    if not process.is_alive():
                        try:
                            payload = result_queue.get(timeout=1)
                        except queue.Empty as exc:
                            raise PyAxiDrawClientError(
                                "AxiDraw plot worker exited without a result "
                                f"(exit code {process.exitcode})."
                            ) from exc
            process.join(timeout=1)
            if payload.get("ok") is not True:
                raise PyAxiDrawClientError(
                    str(payload.get("error") or "AxiDraw plot worker failed.")
                )
            return AxiDrawPlotExecution(**payload["execution"])
        finally:
            with self._lock:
                if self._active_process is process:
                    self._active_process = None
                    self._stop_requested = False
            result_queue.close()

    def request_stop(self) -> bool:
        with self._lock:
            process = self._active_process
            if process is None or not process.is_alive() or process.pid is None:
                return False
            if self._stop_requested:
                return True
            self._stop_requested = True
            self._signal_sender(process.pid, signal.SIGINT)
            return True


class InlineAxiDrawPlotRunner:
    """Compatibility runner for injected clients used outside the real adapter factory."""

    def __init__(self, client) -> None:
        self._client = client

    def run(self, svg_text: str) -> AxiDrawPlotExecution:
        return self._client.run_plot_document(svg_text)

    def request_stop(self) -> bool:
        return False


def _run_plot_worker(settings: dict, svg_text: str, result_queue) -> None:
    try:
        client = PyAxiDrawClient(**settings)
        execution = client.run_plot_document(svg_text, interruptible=True)
        result_queue.put({"ok": True, "execution": asdict(execution)})
    except BaseException as exc:
        result_queue.put({"ok": False, "error": str(exc)})
