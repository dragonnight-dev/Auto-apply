import { useCallback, useEffect, useState } from "react";
import { clearHistory, deleteHistoryEntry, getHistory, getStatistics } from "../api.js";

function HistoryTable({ rows, onDelete }) {
  if (rows.length === 0) return <p className="empty">No history for this client.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">URL</th>
            <th scope="col">Time</th>
            <th scope="col">Result</th>
            <th scope="col"><span className="sr-only">Delete</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="url-cell" title={row.url}>
                <a href={row.url} target="_blank" rel="noreferrer noopener">{row.url}</a>
              </td>
              <td>{new Date(row.time).toLocaleString()}</td>
              <td><span className={`badge badge-${row.status}`}>{row.status}</span></td>
              <td className="cell-end">
                <button type="button" onClick={() => onDelete(row.id)} aria-label={`Delete history entry for ${row.url}`}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Statistics({ token, refreshKey }) {
  const [clients, setClients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const stats = await getStatistics(token);
      setClients(stats.clients);
      if (selected !== null) setHistory((await getHistory(token, selected)).history);
      setError("");
    } catch (failure) {
      setError(failure.message);
    }
  }, [token, selected]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function run(change) {
    try {
      await change();
      await load();
    } catch (failure) {
      setError(failure.message);
    }
  }

  const selectedClient = clients.find((client) => client.client_id === selected);

  return (
    <div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Client</th>
              <th scope="col" className="num">Total</th>
              <th scope="col" className="num">Filled</th>
              <th scope="col" className="num">Partial</th>
              <th scope="col" className="num">Failed</th>
              <th scope="col"><span className="sr-only">History</span></th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.client_id}>
                <td>{client.email}</td>
                <td className="num">{client.total}</td>
                <td className="num">{client.filled}</td>
                <td className="num">{client.partial}</td>
                <td className="num">{client.failed}</td>
                <td className="cell-end">
                  <button type="button" onClick={() => setSelected(client.client_id)}
                    aria-label={`Show history for ${client.email}`}>
                    History
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedClient && (
        <section className="history">
          <div className="section-head">
            <h3>History: {selectedClient.email}</h3>
            {history.length > 0 && (
              <button type="button" onClick={() => {
                if (window.confirm(`Delete all history for ${selectedClient.email}?`)) {
                  run(() => clearHistory(token, selected));
                }
              }}>
                Delete all
              </button>
            )}
          </div>
          <HistoryTable rows={history} onDelete={(id) => run(() => deleteHistoryEntry(token, id))} />
        </section>
      )}
    </div>
  );
}
