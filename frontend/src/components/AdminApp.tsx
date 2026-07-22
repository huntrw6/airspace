import { useState } from "react";
import { api } from "../api";

export function AdminApp() {
  const [password, setPassword] = useState("");
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");
  async function load() {
    try {
      setSummary(await api.adminSummary(password));
      setMessage("");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Admin access failed.",
      );
    }
  }
  return (
    <main>
      <header>
        <span className="brand">AIRSPACE ADMIN</span>
      </header>
      <section>
        <h1>Operations</h1>
        <p>
          Coordinates and push endpoints are intentionally excluded from this
          view.
        </p>
        {!summary && (
          <div className="card">
            <label>
              Administrator password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button onClick={load}>Open dashboard</button>
          </div>
        )}
        {summary && (
          <>
            <pre className="admin-summary">
              {JSON.stringify(summary, null, 2)}
            </pre>
            <button onClick={load}>Refresh</button>
            <button
              onClick={async () => {
                const result = await api.adminCleanup(password);
                setMessage(`Cleanup finished: ${JSON.stringify(result)}`);
                await load();
              }}
            >
              Run retention cleanup
            </button>
          </>
        )}
        {message && <p role="status">{message}</p>}
      </section>
    </main>
  );
}
