// @vitest-environment jsdom
import { render, waitFor } from "@/test/render";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("SwRegister", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("registers /sw.js when service workers are available", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", undefined);
    const register = vi.fn();
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { register },
    });
    const { default: SwRegister } = await import("./sw-register");

    render(<SwRegister />);

    await waitFor(() => expect(register).toHaveBeenCalledWith("/sw.js"));
  });

  it("does not register when mock mode owns the service worker scope", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "1");
    const register = vi.fn();
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { register },
    });
    const { default: SwRegister } = await import("./sw-register");

    render(<SwRegister />);

    expect(register).not.toHaveBeenCalled();
  });
});
