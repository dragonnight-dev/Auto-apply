import { useState } from "react";
import { setClientEnabled } from "./api.js";
import AuthScreen from "./components/AuthScreen.jsx";
import ClientsTable from "./components/ClientsTable.jsx";
import SessionPanel from "./components/SessionPanel.jsx";
import Statistics from "./components/Statistics.jsx";
import { loadToken, saveToken } from "./session.js";
import { useServerState } from "./useServerState.js";

function Console({ token, onSignOut, WebSocketImpl }) {
  const { clients, session, online, notice, setNotice, send } = useServerState(token, {
    onAuthFailed: onSignOut,
    WebSocketImpl,
  });

  async function toggle(client, enabled) {
    try {
      await setClientEnabled(token, client.id, enabled);
    } catch (failure) {
      setNotice(failure.message);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <h1>Auto Apply Console</h1>
        <span className="server-state">
          <span className={`dot ${online ? "dot-on" : "dot-off"}`} aria-hidden="true" />
          {online ? "Server connected" : "Reconnecting…"}
        </span>
        <button type="button" onClick={onSignOut}>Sign out</button>
      </header>
      {notice && <p className="error" role="alert">{notice}</p>}
      <main>
        <section>
          <h2>Clients</h2>
          <ClientsTable clients={clients} onToggle={toggle} onSync={(url) => send({ type: "sync", url })} />
        </section>
        <section>
          <h2>Current page</h2>
          <SessionPanel session={session} clients={clients} onFill={(id) => send({ type: "fill", session_id: id })} />
        </section>
        <section>
          <h2>Statistics</h2>
          <Statistics token={token} refreshKey={`${session?.id}-${session?.state}-${clients.length}`} />
        </section>
      </main>
    </div>
  );
}

export default function App({ WebSocketImpl }) {
  const [token, setToken] = useState(loadToken);

  function update(next) {
    saveToken(next);
    setToken(next);
  }

  if (!token) return <AuthScreen onSignedIn={update} />;
  return <Console token={token} onSignOut={() => update("")} WebSocketImpl={WebSocketImpl} />;
}
