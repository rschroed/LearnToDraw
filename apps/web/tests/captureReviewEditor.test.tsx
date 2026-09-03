import { fireEvent, render, screen } from "@testing-library/react";

import {
  CaptureReviewEditor,
  mapClientPointToCapture,
} from "../src/features/plot-workflow/CaptureReviewEditor";
import type { CaptureMetadata, CaptureReview } from "../src/types/hardware";

const proposedCorners = {
  top_left: [80, 60] as [number, number],
  top_right: [1520, 60] as [number, number],
  bottom_right: [1520, 1140] as [number, number],
  bottom_left: [80, 1140] as [number, number],
};

const capture: CaptureMetadata = {
  id: "capture-editor",
  timestamp: "2026-09-02T12:00:00Z",
  file_path: "/tmp/capture-editor.jpg",
  public_url: "/captures/capture-editor.jpg",
  width: 1600,
  height: 1200,
  mime_type: "image/jpeg",
  review: null,
  normalized: null,
};

const review: CaptureReview = {
  registration_version: 2,
  review_mode: "manual_corners",
  review_required: true,
  review_status: "pending",
  proposed_corners: proposedCorners,
  confirmed_corners: null,
  confirmation_source: null,
};

function installLetterboxedTransform(svg: SVGSVGElement) {
  Object.defineProperty(svg, "getScreenCTM", {
    configurable: true,
    value: () => ({ inverse: () => ({}) }),
  });
  Object.defineProperty(svg, "createSVGPoint", {
    configurable: true,
    value: () => {
      const point = {
        x: 0,
        y: 0,
        matrixTransform: () => ({ x: point.x * 4, y: (point.y - 50) * 4 }),
      };
      return point;
    },
  });
}

describe("manual capture registration editor", () => {
  it("converts client coordinates through the SVG screen matrix and letterboxing", () => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    installLetterboxedTransform(svg);

    expect(mapClientPointToCapture(svg, 100, 100, 1600, 1200)).toEqual([400, 200]);
    expect(mapClientPointToCapture(svg, -10, 20, 1600, 1200)).toEqual([0, 0]);
  });

  it("supports click, drag, keyboard nudge, reset, and confirmation", async () => {
    Object.defineProperty(window, "PointerEvent", {
      configurable: true,
      value: MouseEvent,
    });
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <CaptureReviewEditor
        capture={capture}
        review={review}
        busy={false}
        error={null}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /register page/i }));
    const svg = screen.getAllByLabelText(
      /captured page with registration corners/i,
    )[1] as unknown as SVGSVGElement;
    installLetterboxedTransform(svg);

    fireEvent.pointerDown(svg, { clientX: 100, clientY: 100 });
    expect(
      screen
        .getByRole("button", { name: /top left corner/i })
        .querySelector(".capture-review-handle"),
    ).toHaveAttribute("cx", "400");
    expect(
      screen
        .getByRole("button", { name: /top left corner/i })
        .querySelector(".capture-review-handle"),
    ).toHaveAttribute("cy", "200");
    fireEvent.click(screen.getByRole("button", { name: /^top right$/i }));
    const topRightHandle = screen.getByRole("button", { name: /top right corner/i });
    Object.defineProperty(topRightHandle, "setPointerCapture", {
      configurable: true,
      value: vi.fn(),
    });
    fireEvent.pointerDown(topRightHandle, { clientX: 320, clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(svg, { clientX: 330, clientY: 105, pointerId: 1 });
    fireEvent.pointerUp(svg, { pointerId: 1 });
    expect(topRightHandle.querySelector(".capture-review-handle")).toHaveAttribute("cx", "1320");
    expect(topRightHandle.querySelector(".capture-review-handle")).toHaveAttribute("cy", "220");
    fireEvent.keyDown(screen.getByRole("button", { name: /^bottom left$/i }), {
      key: "ArrowRight",
    });

    fireEvent.click(screen.getByRole("button", { name: /^reset$/i }));
    fireEvent.keyDown(screen.getByRole("button", { name: /^top left$/i }), {
      key: "ArrowDown",
    });
    fireEvent.click(screen.getByRole("button", { name: /register capture/i }));

    expect(onConfirm).toHaveBeenCalledWith({
      ...proposedCorners,
      top_left: [80, 61],
    });
  });

  it("shows backend errors without closing and disables actions while busy", () => {
    const { rerender } = render(
      <CaptureReviewEditor
        capture={capture}
        review={review}
        busy={false}
        error="The page corners form a crossed quadrilateral."
        onConfirm={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /register page/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/crossed quadrilateral/i);
    expect(screen.getByRole("dialog", { name: /register captured page/i })).toBeInTheDocument();

    rerender(
      <CaptureReviewEditor
        capture={capture}
        review={review}
        busy
        error="The page corners form a crossed quadrilateral."
        onConfirm={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    expect(screen.getByRole("button", { name: /registering/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^reset$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^top right$/i })).toBeDisabled();
  });

  it("keeps the modal and draft open when polling returns equivalent review data", () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <CaptureReviewEditor
        capture={capture}
        review={review}
        busy={false}
        error={null}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /register page/i }));
    fireEvent.keyDown(screen.getByRole("button", { name: /^top left$/i }), {
      key: "ArrowRight",
    });

    rerender(
      <CaptureReviewEditor
        capture={{ ...capture }}
        review={{
          ...review,
          proposed_corners: structuredClone(proposedCorners),
        }}
        busy={false}
        error={null}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByRole("dialog", { name: /register captured page/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /register capture/i }));
    expect(onConfirm).toHaveBeenCalledWith({
      ...proposedCorners,
      top_left: [81, 60],
    });
  });

  it("keeps footer actions inside the modal panel scroll container", () => {
    render(
      <CaptureReviewEditor
        capture={capture}
        review={review}
        busy={false}
        error={null}
        onConfirm={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /register page/i }));

    const dialog = screen.getByRole("dialog", { name: /register captured page/i });
    const panel = dialog.querySelector(".capture-review-modal-panel");
    const confirmButton = screen.getByRole("button", { name: /register capture/i });

    expect(panel).not.toBeNull();
    expect(panel).toHaveClass("capture-review-modal-panel");
    expect(panel).toContainElement(confirmButton);
  });
});
