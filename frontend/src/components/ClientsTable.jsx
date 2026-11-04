const ACTION_LABELS = { syncing: "Syncing", filling: "Filling", "no-action": "No action" };

function ClientRow({ client, onSync, onToggle }) {
  return (
    <tr className={client.enabled ? "" : "row-disabled"}>
      <td>
        <strong>{client.name || client.email}</strong>
        {client.name && <div className="muted">{client.email}</div>}
      </td>
      <td>
        <span className={`dot ${client.connected ? "dot-on" : "dot-off"}`} aria-hidden="true" />
        {client.connected ? "Connected" : "Offline"}
      </td>
      <td className="url-cell" title={client.url}>{client.url || <span className="muted">No page reported</span>}</td>
      <td>{ACTION_LABELS[client.action] || client.action}</td>
      <td>
        <label className="toggle">
          <input
            type="checkbox"
            checked={client.enabled}
            onChange={(event) => onToggle(client, event.target.checked)}
            aria-label={`Enable ${client.email}`}
          />
          {client.enabled ? "Enabled" : "Disabled"}
        </label>
      </td>
      <td className="row-action">
        {client.url && (
          <button type="button" onClick={() => onSync(client.url)} aria-label={`Sync all clients to ${client.email}'s URL`}>
            Sync URL
          </button>
        )}
      </td>
    </tr>
  );
}

export default function ClientsTable({ clients, onSync, onToggle }) {
  if (clients.length === 0) {
    return <p className="empty">No clients yet. They appear here after signing up in the Chrome extension.</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Client</th>
            <th scope="col">Connection</th>
            <th scope="col">Current URL</th>
            <th scope="col">Action</th>
            <th scope="col">State</th>
            <th scope="col"><span className="sr-only">Sync</span></th>
          </tr>
        </thead>
        <tbody>
          {clients.map((client) => (
            <ClientRow key={client.id} client={client} onSync={onSync} onToggle={onToggle} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
