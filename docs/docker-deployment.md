# Docker deployment

The multi-stage image builds the React frontend and installs the Python service, then runs as UID
10001 with only port 8000 and `/app/data` writable. Compose persists SQLite in a named volume and
uses live/readiness health checks with `unless-stopped`. Configure HTTPS at a reverse proxy, set
Secure cookies, use independent random admin/session secrets, back up while SQLite is quiescent, and
test restoration before upgrades. Commands are maintained in the root README.

The retention worker runs even when the flight provider is disabled. Configure
`AIRSPACE_HISTORY_RETENTION_DAYS`, `AIRSPACE_INACTIVE_PROFILE_DAYS`,
`AIRSPACE_INVALID_SUBSCRIPTION_RETENTION_DAYS`, and `AIRSPACE_CLEANUP_INTERVAL_SECONDS` in `.env`.
The protected operations console is available at `/admin`; additionally restrict it at the proxy.
