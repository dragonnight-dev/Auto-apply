import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import AuthScreen from "./AuthScreen.jsx";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(status, body) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

it("signs in without asking for a boss key", async () => {
  const fetchMock = stubFetch(200, { token: "tok" });
  const onSignedIn = vi.fn();
  render(<AuthScreen onSignedIn={onSignedIn} />);
  expect(screen.queryByLabelText("Boss key")).not.toBeInTheDocument();

  await userEvent.type(screen.getByLabelText("Username"), "boss");
  await userEvent.type(screen.getByLabelText("Password"), "long-enough");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(fetchMock.mock.calls[0][0]).toBe("/api/boss/signin");
  expect(onSignedIn).toHaveBeenCalledWith("tok");
});

it("signs up with the boss key", async () => {
  const fetchMock = stubFetch(201, { token: "tok" });
  const onSignedIn = vi.fn();
  render(<AuthScreen onSignedIn={onSignedIn} />);

  await userEvent.click(screen.getByRole("button", { name: /boss key/ }));
  await userEvent.type(screen.getByLabelText("Username"), "boss");
  await userEvent.type(screen.getByLabelText("Password"), "long-enough");
  await userEvent.type(screen.getByLabelText("Boss key"), "the-key");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));

  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/boss/signup");
  expect(JSON.parse(options.body)).toEqual({ username: "boss", password: "long-enough", boss_key: "the-key" });
  expect(onSignedIn).toHaveBeenCalledWith("tok");
});

it("shows the server's error and allows another try", async () => {
  stubFetch(401, { error: "Incorrect username or password." });
  const onSignedIn = vi.fn();
  render(<AuthScreen onSignedIn={onSignedIn} />);
  await userEvent.type(screen.getByLabelText("Username"), "boss");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect username or password.");
  expect(onSignedIn).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
});
