const STATE_TEXT = {
  syncing: "Opening the page on all clients…",
  planning: "Creating fill data with the local model…",
  ready: "Fill data is ready to send.",
  filling: "Clients are filling the form…",
  done: "Finished. Review each client's form before submitting it.",
  failed: "This sync did not complete.",
};
const SKIP_REASONS = {
  sensitive: "sensitive question, left for the applicant",
  needs_person: "needs the applicant's own agreement",
  no_answer: "not answered by the profile",
  unverified_answer: "the model's answer could not be verified",
  slm_unavailable: "model unavailable",
  unsupported_file: "only resumes are uploaded",
  too_many_long_answers: "too many long questions",
  plan_error: "could not create fill data",
};

function PlanRow({ plan, client }) {
  return (
    <li>
      <div className="plan-head">
        <strong>{client ? client.email : `Client ${plan.client_id}`}</strong>
        <span className={`badge badge-${plan.status}`}>{plan.status}</span>
        <span className="muted">{plan.actions} to fill, {plan.skipped.length} skipped</span>
      </div>
      {plan.skipped.length > 0 && (
        <details>
          <summary>Skipped fields</summary>
          <ul className="skipped">
            {plan.skipped.map((item, index) => (
              <li key={`${item.selector}-${index}`}>
                {item.label || item.selector}: {SKIP_REASONS[item.reason] || item.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

export default function SessionPanel({ session, clients, onFill }) {
  if (!session) {
    return <p className="empty">Hover over a client and choose Sync URL to start.</p>;
  }
  const clientsById = new Map(clients.map((client) => [client.id, client]));
  return (
    <div className="session">
      <div className="session-head">
        <div className="session-text">
          <div className="session-title">{session.title || session.url}</div>
          <div className="muted url-cell" title={session.url}>{session.url}</div>
          <p role="status">{session.error || STATE_TEXT[session.state]}</p>
        </div>
        <button className="primary" type="button" disabled={session.state !== "ready"} onClick={() => onFill(session.id)}>
          Fill data
        </button>
      </div>
      {session.plans.length > 0 && (
        <ul className="plans">
          {session.plans.map((plan) => (
            <PlanRow key={plan.id} plan={plan} client={clientsById.get(plan.client_id)} />
          ))}
        </ul>
      )}
    </div>
  );
}
