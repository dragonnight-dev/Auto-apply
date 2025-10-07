import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import ClientsTable from "./ClientsTable.jsx";

const client = (overrides = {}) => ({
  id: 1, email: "ann@example.com", name: "Ann Lee", enabled: true, connected: true,
  url: "https://jobs.example/1", action: "no-action", ...overrides,
});

it("shows connection, URL and current action", () => {
  render(<ClientsTable clients={[client({ action: "syncing" }), client({ id: 2, email: "b@example.com", name: "",
    connected: false, url: "", action: "filling" })]} onSync={vi.fn()} onToggle={vi.fn()} />);
  expect(screen.getByText("Ann Lee")).toBeInTheDocument();
  expect(screen.getByText("Connected")).toBeInTheDocument();
  expect(screen.getByText("Offline")).toBeInTheDocument();
  expect(screen.getByText("https://jobs.example/1")).toBeInTheDocument();
  expect(screen.getByText("Syncing")).toBeInTheDocument();
  expect(screen.getByText("Filling")).toBeInTheDocument();
});

it("syncs all clients to the selected row's URL", async () => {
  const onSync = vi.fn();
  render(<ClientsTable clients={[client()]} onSync={onSync} onToggle={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: /Sync all clients/ }));
  expect(onSync).toHaveBeenCalledWith("https://jobs.example/1");
});

it("offers no sync when a client has no URL", () => {
  render(<ClientsTable clients={[client({ url: "" })]} onSync={vi.fn()} onToggle={vi.fn()} />);
  expect(screen.queryByRole("button", { name: /Sync all clients/ })).not.toBeInTheDocument();
});

it("toggles a client on and off", async () => {
  const onToggle = vi.fn();
  const row = client();
  render(<ClientsTable clients={[row]} onSync={vi.fn()} onToggle={onToggle} />);
  await userEvent.click(screen.getByRole("checkbox", { name: "Enable ann@example.com" }));
  expect(onToggle).toHaveBeenCalledWith(row, false);
});

it("explains the empty state", () => {
  render(<ClientsTable clients={[]} onSync={vi.fn()} onToggle={vi.fn()} />);
  expect(screen.getByText(/No clients yet/)).toBeInTheDocument();
});

it("renders page-supplied URLs as text, not markup", () => {
  const { container } = render(<ClientsTable clients={[client({ url: "https://x/<img src=x>" })]} onSync={vi.fn()}
    onToggle={vi.fn()} />);
  expect(container.querySelector("img")).toBeNull();
});
