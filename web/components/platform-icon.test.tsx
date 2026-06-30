import { render, screen } from "@/test/render";
import { describe, expect, it } from "vitest";
import { PlatformBadge, PlatformGlyph } from "./platform-icon";

describe("platform icon helpers", () => {
  it.each([
    ["https://www.youtube.com/watch?v=abc", "long", "YouTube source"],
    ["https://www.youtube.com/shorts/abc", "short", "YouTube Shorts source"],
    ["https://youtu.be/abc", "long", "YouTube source"],
    ["https://www.tiktok.com/@vig/video/1", "short", "TikTok source"],
    ["https://www.instagram.com/reel/1", "short", "Instagram source"],
    ["https://github.com/example/repo", "repo", "GitHub source"],
    ["https://example.com/post", "article", "example.com source"],
  ])("renders %s as %s", (url, contentType, label) => {
    render(<PlatformBadge url={url} contentType={contentType} />);

    const badge = screen.getByLabelText(label);
    expect(badge).toHaveClass("border-line");
    expect(badge.querySelector("svg,img")).toBeTruthy();
  });

  it("renders an article glyph with favicon or document fallback", () => {
    render(<PlatformGlyph url="https://example.com/post" contentType="article" />);

    expect(document.querySelector("img,svg")).toBeTruthy();
  });
});
