import { render } from "@/test/render";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { PreviewCard } from "./preview-card";
import type { JobSummary } from "./job-card";

vi.mock("next/link", () => ({
  default: ({ href, children, className, "aria-label": ariaLabel }: { href: string; children?: ReactNode; className?: string; "aria-label"?: string }) => (
    <a href={href} className={className} aria-label={ariaLabel}>
      {children}
    </a>
  ),
}));

const baseJob: JobSummary = {
  id: "job_1",
  title: "Some article",
  url: "https://example.com/post",
  content_type: "article",
  status: "done",
  created_at: "2026-06-13T10:00:00.000Z",
};

describe("PreviewCard", () => {
  it("shows a platform icon for non-short content types, not just short", () => {
    // width=16 identifies the title-row glyph specifically, distinct from the
    // size=22 favicon the thumbnail's "no preview" placeholder always renders.
    const { container } = render(<PreviewCard job={baseJob} index={0} />);
    expect(
      container.querySelector('img[width="16"][src*="s2/favicons"]'),
    ).toBeInTheDocument();
  });

  it("still drops the title-row icon in compact (Short grid) mode", () => {
    const { container } = render(
      <PreviewCard job={baseJob} index={0} variant="compact" />,
    );
    expect(container.querySelector('img[width="16"][src*="s2/favicons"]')).not.toBeInTheDocument();
  });
});
