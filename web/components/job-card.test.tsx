import { render, screen } from "@/test/render";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { JobCard, type JobSummary } from "./job-card";

vi.mock("next/link", () => ({
  default: ({ href, children, className, "aria-label": ariaLabel }: { href: string; children?: ReactNode; className?: string; "aria-label"?: string }) => (
    <a href={href} className={className} aria-label={ariaLabel}>
      {children}
    </a>
  ),
}));

const baseJob: JobSummary = {
  id: "job_1",
  title: "Platform source row",
  url: "https://www.tiktok.com/@vig/video/1",
  content_type: "short",
  status: "done",
  created_at: "2026-06-13T10:00:00.000Z",
};

describe("JobCard", () => {
  it("shows the status badge before the platform icon", () => {
    render(<JobCard job={baseJob} />);

    const status = screen.getByText("done");
    const platform = screen.getByLabelText("TikTok source");
    const badgeRow = status.parentElement;

    expect(badgeRow).toBe(platform.parentElement);
    const children = Array.from(badgeRow?.children ?? []);
    expect(children.indexOf(status)).toBeLessThan(children.indexOf(platform));
  });

  it("renders the tag dropdown on its own row under the badges", () => {
    render(<JobCard job={baseJob} />);
    const status = screen.getByText("done");
    const tagButton = screen.getByLabelText("Tags");
    // Tag row is a sibling of the badge row, not inside it.
    expect(status.parentElement?.contains(tagButton)).toBe(false);
    expect(tagButton).toBeTruthy();
  });
});
