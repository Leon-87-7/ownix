import { afterEach, describe, expect, it, vi } from "vitest";
import { buildThumbnailHints, fetchFeedThumbnails } from "./feed-thumbnail-preload";

const items = [{ thumbnail_url: "https://img.youtube.com/one.jpg" }];

function thumbs(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    thumbnail_url: `https://img.youtube.com/vi/${index}/hqdefault.jpg`,
  }));
}

afterEach(() => vi.restoreAllMocks());

describe("buildThumbnailHints", () => {
  it("always emits the two static preconnects, even with no thumbnails", () => {
    expect(buildThumbnailHints([])).toEqual([
      { kind: "preconnect", href: "https://img.youtube.com" },
      { kind: "preconnect", href: "https://opengraph.githubassets.com" },
    ]);
  });

  it("preloads at most ten thumbnails, first four high priority", () => {
    const hints = buildThumbnailHints(thumbs(12));
    const preloads = hints.filter((h) => h.kind === "preload");

    expect(preloads).toHaveLength(10);
    preloads.forEach((hint, index) => {
      if (hint.kind !== "preload") throw new Error("expected preload");
      expect(hint.highPriority).toBe(index < 4);
    });
  });

  it("skips jobs with no thumbnail_url without consuming a preload slot", () => {
    const hints = buildThumbnailHints([
      { thumbnail_url: "https://img.youtube.com/a.jpg" },
      { thumbnail_url: null },
      { thumbnail_url: "https://img.youtube.com/b.jpg" },
    ]);
    const preloadHrefs = hints
      .filter((h) => h.kind === "preload")
      .map((h) => (h.kind === "preload" ? h.href : ""));

    expect(preloadHrefs).toEqual([
      "https://img.youtube.com/a.jpg",
      "https://img.youtube.com/b.jpg",
    ]);
  });
});

describe("fetchFeedThumbnails", () => {
  it("fetches the owned feed when a session cookie is present", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items }), { status: 200 }),
    );

    await expect(
      fetchFeedThumbnails({
        sessionCookie: "session",
        previewCookie: "1",
        cookieHeader: "vig_session=session; ownix_preview=1",
      }),
    ).resolves.toEqual(items);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/jobs?limit=10",
      expect.objectContaining({
        headers: { cookie: "vig_session=session; ownix_preview=1" },
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("fetches the preview feed when only the preview cookie is present", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items }), { status: 200 }),
    );

    await fetchFeedThumbnails({ previewCookie: "1", cookieHeader: "ownix_preview=1" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/preview/jobs?limit=10",
      expect.any(Object),
    );
  });

  it("does not fetch without an eligible cookie", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    await expect(fetchFeedThumbnails({ cookieHeader: "" })).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("suppresses fetch failures so the feed shell can render", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("timed out"));
    await expect(
      fetchFeedThumbnails({ sessionCookie: "session", cookieHeader: "vig_session=session" }),
    ).resolves.toBeNull();
  });
});
