import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NoPreviewRing, ringGeometry } from "./no-preview-ring";

describe("NoPreviewRing", () => {
  it("geometry is deterministic per seed and stays in bounds", () => {
    const a = ringGeometry("job-1");
    expect(ringGeometry("job-1")).toEqual(a);
    expect(ringGeometry("job-2")).not.toEqual(a);
    expect(a.size).toBeGreaterThanOrEqual(112);
    expect(a.size).toBeLessThanOrEqual(176);
    // center hugs one edge: exactly one axis is edge-relative (px/calc)
    const edgy = [a.left, a.top].filter((v) => !/^\d+%$/.test(v));
    expect(edgy).toHaveLength(1);
  });

  it("renders decorative ring text with the pipeline type", () => {
    const { container } = render(<NoPreviewRing seed="job-1" label="link" />);
    const root = container.firstElementChild;
    expect(root).toHaveAttribute("aria-hidden", "true");
    expect(root?.textContent).toContain("◉ NO PREVIEW ◉ LINK");
  });
});
