import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { JobCard, type JobSummary } from "./job-card";

vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
    <a href={href} className={className}>
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
  it("shows a platform badge before the existing type and status badges", () => {
    render(<JobCard job={baseJob} />);

    expect(screen.getByLabelText("TikTok source")).toHaveTextContent("TikTok");
    expect(screen.getByText("short")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument();
  });
});
