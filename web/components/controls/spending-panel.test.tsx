// @vitest-environment jsdom
import { render, screen, waitFor } from "@/test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SpendingPanel } from "./spending-panel";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

const SUMMARY = {
  currency: "USD",
  daily_limit_micros: 500_000,
  monthly_limit_micros: 3_000_000,
  allow_paid_gemini: false,
  enabled: true,
  daily_spent_micros: 0,
  monthly_spent_micros: 0,
  daily_remaining_micros: 500_000,
  monthly_remaining_micros: 3_000_000,
};

function mockSpending(isOperator: boolean) {
  const puts: Record<string, unknown>[] = [];
  vi.spyOn(global, "fetch").mockImplementation((input, init) => {
    if (String(input) !== "/api/controls/spending")
      return Promise.reject(new Error(`unexpected fetch: ${String(input)}`));
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      puts.push(body);
      return Promise.resolve(jsonResponse(body));
    }
    return Promise.resolve(
      jsonResponse({ ...SUMMARY, is_operator: isOperator }),
    );
  });
  return puts;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("SpendingPanel", () => {
  it("shows no controls to a non-operator", async () => {
    mockSpending(false);
    render(<SpendingPanel />);
    expect(
      await screen.findByText(/contact the operator/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText(/allow paid gemini/i),
    ).not.toBeInTheDocument();
  });

  it("lets the operator enable paid Gemini", async () => {
    const puts = mockSpending(true);
    render(<SpendingPanel />);
    await userEvent.click(await screen.findByLabelText(/allow paid gemini/i));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toMatchObject({ allow_paid_gemini: true, enabled: true });
    expect(await screen.findByRole("status")).toHaveTextContent(/enabled/i);
  });

  it("saves an edited limit in micros, and empty as no limit", async () => {
    const puts = mockSpending(true);
    render(<SpendingPanel />);
    const daily = await screen.findByLabelText(/daily limit/i);
    await userEvent.clear(daily);
    await userEvent.type(daily, "1.25{Enter}");
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toMatchObject({ daily_limit_micros: 1_250_000 });

    const monthly = screen.getByLabelText(/monthly limit/i);
    await userEvent.clear(monthly);
    await userEvent.tab();
    await waitFor(() => expect(puts).toHaveLength(2));
    expect(puts[1]).toMatchObject({ monthly_limit_micros: null });
  });
});
