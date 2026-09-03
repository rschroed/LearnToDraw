import {
  getWorkspaceMetrics,
  getWorkspaceValidation,
} from "../src/features/hardware/hardwareDashboardUtils";

describe("workspace validation", () => {
  const axidrawSafeBounds = { width_mm: 289.974, height_mm: 207.932 };

  it("allows US Letter landscape paper when margins keep drawing inside safe bounds", () => {
    const workspace = getWorkspaceMetrics({
      pageWidthMm: "279.4",
      pageHeightMm: "215.9",
      marginLeftMm: "10",
      marginTopMm: "10",
      marginRightMm: "10",
      marginBottomMm: "10",
    });

    expect(getWorkspaceValidation(workspace, axidrawSafeBounds)).toBeNull();
  });

  it("rejects paper margins that leave drawable coordinates outside safe bounds", () => {
    const workspace = getWorkspaceMetrics({
      pageWidthMm: "279.4",
      pageHeightMm: "215.9",
      marginLeftMm: "5",
      marginTopMm: "5",
      marginRightMm: "5",
      marginBottomMm: "5",
    });

    expect(getWorkspaceValidation(workspace, axidrawSafeBounds)).toBe(
      "Drawable area exceeds the plotter's safe bounds of 289.974 x 207.932 mm. Increase the right or bottom margin.",
    );
  });
});
