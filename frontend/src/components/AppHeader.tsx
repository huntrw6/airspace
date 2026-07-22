export type ConnectionState = "checking" | "live" | "disconnected";

export function AppHeader({ connectionState }: { connectionState: ConnectionState }) {
  const label =
    connectionState === "live"
      ? "LIVE"
      : connectionState === "disconnected"
        ? "DISCONNECTED"
        : "CONNECTING";

  return (
    <header>
      <span className="brand dashboard-brand">YOUR AIRSPACE</span>
      <span className={`status status-${connectionState}`} role="status">
        <span className="status-dot" aria-hidden="true">●</span>{" "}
        {label}
      </span>
    </header>
  );
}
