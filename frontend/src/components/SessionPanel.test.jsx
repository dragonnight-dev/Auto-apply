import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import SessionPanel from "./SessionPanel.jsx";

const session = (overrides = {}) => ({
  id: 7, url: "https://jobs.example/1", state: "ready", error: "", title: "Engineer",
  plans: [{ id: 1, client_id: 1, status: "ready", actions: 4,
    skipped: [{ selector: "#g", label: "Gender", reason: "sensitive" }] }],
  ...overrides,
});
const clients = [{ id: 1, email: "ann@example.com" }];

it("prompts when nothing has been synced", () => {
  render(<SessionPanel session={null} clients={[]} onFill={vi.fn()} />);
  expect(screen.getByText(/Sync URL to start/)).toBeInTheDocument();
});

it("sends fill data when ready", async () => {
  const onFill = vi.fn();
  render(<SessionPanel session={session()} clients={clients} onFill={onFill} />);
  await userEvent.click(screen.getByRole("button", { name: "Fill data" }));
  expect(onFill).toHaveBeenCalledWith(7);
});

it.each(["syncing", "planning", "filling", "done", "failed"])("cannot fill while %s", (state) => {
  render(<SessionPanel session={session({ state })} clients={clients} onFill={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Fill data" })).toBeDisabled();
});

it("shows per-client results and why fields were skipped", () => {
  render(<SessionPanel session={session()} clients={clients} onFill={vi.fn()} />);
  expect(screen.getByText("ann@example.com")).toBeInTheDocument();
  expect(screen.getByText("4 to fill, 1 skipped")).toBeInTheDocument();
  expect(screen.getByText(/Gender: sensitive question/)).toBeInTheDocument();
});

it("shows the failure reason", () => {
  render(<SessionPanel session={session({ state: "failed", error: "The page took too long to load." })} clients={clients}
    onFill={vi.fn()} />);
  expect(screen.getByRole("status")).toHaveTextContent("The page took too long to load.");
});

it("tells the boss a finished form still needs review", () => {
  render(<SessionPanel session={session({ state: "done" })} clients={clients} onFill={vi.fn()} />);
  expect(screen.getByRole("status")).toHaveTextContent(/before submitting/);
});
