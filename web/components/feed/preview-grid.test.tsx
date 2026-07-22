import { render, screen } from "@/test/render";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { PreviewGrid } from "./preview-grid";
import type { JobSummary } from "./job-card";

vi.mock("next/link", () => ({
  default: ({ href, children, className, "aria-label": ariaLabel }: { href: string; children?: ReactNode; className?: string; "aria-label"?: string }) => (
    <a href={href} className={className} aria-label={ariaLabel}>
      {children}
    </a>
  ),
}));

const portraitJob: JobSummary = {
  id: "job_p",
  title: "Portrait short",
  url: "https://www.tiktok.com/@vig/video/1",
  content_type: "short",
  status: "done",
  created_at: "2026-07-22T10:00:00.000Z",
  thumbnail_kind: "portrait",
};

const landscapeJob: JobSummary = {
  id: "job_l",
  title: "Landscape long",
  url: "https://www.youtube.com/watch?v=abc",
  content_type: "long",
  status: "done",
  created_at: "2026-07-22T09:00:00.000Z",
  thumbnail_kind: "landscape",
};

function cardOf(name: RegExp) {
  return screen.getByRole("link", { name }).parentElement;
}

describe("PreviewGrid", () => {
  it("keeps the uniform 3-up grid by default", () => {
    const { container } = render(
      <PreviewGrid jobs={[landscapeJob]} />,
    );
    expect(container.firstElementChild?.className).toContain("lg:grid-cols-3");
    expect(container.firstElementChild?.className).not.toContain("grid-flow-dense");
  });

  it("bento: packs dense and spans portrait cards twice as tall as landscape", () => {
    const { container } = render(
      <PreviewGrid jobs={[portraitJob, landscapeJob]} variant="bento" />,
    );
    expect(container.firstElementChild?.className).toContain("grid-flow-dense");
    expect(cardOf(/portrait short/i)?.className).toContain("sm:row-span-4");
    expect(cardOf(/landscape long/i)?.className).toContain("sm:row-span-2");
  });

  it("shorts: renders a 5-column ladder with compact cards (no status badge)", () => {
    const { container } = render(
      <PreviewGrid jobs={[portraitJob]} variant="shorts" />,
    );
    const grid = container.firstElementChild;
    expect(grid?.className).toContain("grid-cols-2");
    expect(grid?.className).toContain("sm:grid-cols-3");
    expect(grid?.className).toContain("lg:grid-cols-5");
    expect(screen.queryByText("done")).toBeNull();
  });

  it("shorts: keeps the 9:16 thumbnail uncropped", () => {
    render(<PreviewGrid jobs={[portraitJob]} variant="shorts" />);
    const card = cardOf(/portrait short/i);
    expect(card?.innerHTML).toContain("aspect-[9/16]");
  });

  it("shorts: forces 9:16 even when thumbnail_kind is missing", () => {
    const kindless = { ...portraitJob, thumbnail_kind: null };
    render(<PreviewGrid jobs={[kindless]} variant="shorts" />);
    const card = cardOf(/portrait short/i);
    expect(card?.innerHTML).toContain("aspect-[9/16]");
    expect(card?.innerHTML).not.toContain("aspect-video");
  });
});
