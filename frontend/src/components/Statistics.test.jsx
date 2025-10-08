import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Statistics from "./Statistics.jsx";

let rows;
let calls;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

beforeEach(() => {
  rows = [{ id: 5, client_id: 1, url: "https://jobs.example/1", time: "2025-10-06T08:00:00+00:00", status: "filled" }];
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url, options = {}) => {
    calls.push(`${options.method || "GET"} ${url}`);
    if (url === "/api/stats") {
      return json({ clients: [{ client_id: 1, email: "ann@example.com", total: rows.length, filled: rows.length,
        partial: 0, failed: 0 }] });
    }
    if (options.method === "DELETE") {
      rows = url.includes("?client=") ? [] : rows.filter((row) => !url.endsWith(`/${row.id}`));
      return new Response(null, { status: 204 });
    }
    return json({ history: rows });
  }));
});
afterEach(() => vi.unstubAllGlobals());

const openHistory = async () => {
  render(<Statistics token="tok" refreshKey="1" />);
  await userEvent.click(await screen.findByRole("button", { name: "Show history for ann@example.com" }));
  await screen.findByText("https://jobs.example/1");
};

it("shows each client's counts", async () => {
  render(<Statistics token="tok" refreshKey="1" />);
  expect(await screen.findByText("ann@example.com")).toBeInTheDocument();
  expect(screen.getAllByText("1")).toHaveLength(2);
});

it("opens a client's history with URL, time and result", async () => {
  await openHistory();
  expect(screen.getByText("filled")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "https://jobs.example/1" })).toHaveAttribute("rel", "noreferrer noopener");
  expect(calls).toContain("GET /api/history?client=1");
});

it("deletes one entry and reloads", async () => {
  await openHistory();
  await userEvent.click(screen.getByRole("button", { name: /Delete history entry/ }));
  await screen.findByText("No history for this client.");
  expect(calls).toContain("DELETE /api/history/5");
});

it("asks before deleting everything", async () => {
  await openHistory();
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  await userEvent.click(screen.getByRole("button", { name: "Delete all" }));
  expect(calls).not.toContain("DELETE /api/history?client=1");

  confirm.mockReturnValue(true);
  await userEvent.click(screen.getByRole("button", { name: "Delete all" }));
  await waitFor(() => expect(calls).toContain("DELETE /api/history?client=1"));
  await screen.findByText("No history for this client.");
});

it("reloads when the workflow changes", async () => {
  const { rerender } = render(<Statistics token="tok" refreshKey="1" />);
  await screen.findByText("ann@example.com");
  const before = calls.length;
  rerender(<Statistics token="tok" refreshKey="2" />);
  await waitFor(() => expect(calls.length).toBeGreaterThan(before));
});

it("shows load errors", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ error: "Authentication required." }, 401)));
  render(<Statistics token="tok" refreshKey="1" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Authentication required.");
});
