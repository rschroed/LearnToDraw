from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _configure_pythonpath() -> None:
    script_path = Path(__file__).resolve()
    src_dir = script_path.parents[1] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_configure_pythonpath()

from learn_to_draw_api.services.capture_normalization import (  # noqa: E402
    CaptureNormalizationService,
    target_from_page_size,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay a saved capture through one normalization experiment.",
    )
    parser.add_argument("capture", type=Path, help="Path to the saved raster capture.")
    parser.add_argument(
        "--experiment",
        choices=("region_v2", "contour_v3"),
        default="region_v2",
        help="Normalization experiment to run.",
    )
    parser.add_argument(
        "--mode",
        choices=("default", "region_only"),
        default="default",
        help="Normalization mode to run.",
    )
    parser.add_argument(
        "--page-width-mm",
        type=float,
        default=210.0,
        help="Target page width in millimeters.",
    )
    parser.add_argument(
        "--page-height-mm",
        type=float,
        default=200.0,
        help="Target page height in millimeters.",
    )
    parser.add_argument(
        "--frame-source",
        choices=("prepared_svg", "workspace_drawable_area"),
        default="prepared_svg",
        help="Normalization target frame source.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/learntodraw-normalization-experiment"),
        help="Directory where replay artifacts should be written.",
    )
    return parser


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    capture_path = args.capture.resolve()
    if not capture_path.exists():
        parser.error(f"Capture does not exist: {capture_path}")

    service = CaptureNormalizationService(
        mode=args.mode,
        experiment=args.experiment,
    )
    artifacts = service.normalize(
        content=capture_path.read_bytes(),
        target=target_from_page_size(
            page_width_mm=args.page_width_mm,
            page_height_mm=args.page_height_mm,
            source=args.frame_source,
        ),
    )

    output_root = (args.output_dir / args.experiment / capture_path.stem).resolve()
    _write_bytes(output_root.with_name(f"{capture_path.stem}-rectified-color.png"), artifacts.rectified_color)
    _write_bytes(
        output_root.with_name(f"{capture_path.stem}-rectified-grayscale.png"),
        artifacts.rectified_grayscale,
    )
    _write_bytes(
        output_root.with_name(f"{capture_path.stem}-debug-overlay.png"),
        artifacts.debug_overlay,
    )

    metadata = artifacts.metadata.model_dump(mode="json")
    print(f"capture: {capture_path}")
    print(f"experiment: {args.experiment}")
    print(f"mode: {args.mode}")
    print(f"method: {metadata['method']}")
    print(f"confidence: {metadata['confidence']}")
    frame = metadata.get("frame") or {}
    print(f"frame: {frame.get('kind')} v{frame.get('version')}")
    diagnostics = metadata.get("diagnostics") or {}
    selected = diagnostics.get(args.experiment) or {}
    print(f"primary_status: {selected.get('status')}")
    print(f"primary_rejection_reason: {selected.get('rejection_reason')}")
    print(f"output_dir: {output_root.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
