import { useState } from "react";
import { signIn, signUp } from "../api.js";

export default function AuthScreen({ onSignedIn }) {
  const [mode, setMode] = useState("signin");
  const [form, setForm] = useState({ username: "", password: "", bossKey: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isSignUp = mode === "signup";

  const field = (name) => ({
    value: form[name],
    onChange: (event) => setForm({ ...form, [name]: event.target.value }),
    required: true,
  });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const account = isSignUp
        ? await signUp(form.username, form.password, form.bossKey)
        : await signIn(form.username, form.password);
      onSignedIn(account.token);
    } catch (failure) {
      setError(failure.message);
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <form className="auth-card" onSubmit={submit}>
        <h1>Auto Apply Console</h1>
        <label>
          Username
          <input {...field("username")} autoComplete="username" autoFocus />
        </label>
        <label>
          Password
          <input
            {...field("password")}
            type="password"
            minLength={isSignUp ? 8 : undefined}
            autoComplete={isSignUp ? "new-password" : "current-password"}
          />
        </label>
        {isSignUp && (
          <label>
            Boss key
            <input {...field("bossKey")} type="password" autoComplete="off" />
          </label>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={busy}>
          {isSignUp ? "Create account" : "Sign in"}
        </button>
        <button
          className="link"
          type="button"
          onClick={() => {
            setMode(isSignUp ? "signin" : "signup");
            setError("");
          }}
        >
          {isSignUp ? "I already have an account" : "Create an account with a boss key"}
        </button>
      </form>
    </main>
  );
}
