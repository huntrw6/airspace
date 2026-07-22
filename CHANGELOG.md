# Changelog

## 0.1.0 - 2026-07-21

- Began the standalone Airspace architecture.
- Added anonymous profiles, monitored-location CRUD, push-subscription persistence, health and
  protected administrator endpoints.
- Added typed geographic/lifecycle/provider/polling primitives and tests.
- Added the cautious FlightRadar24 adapter, background regional worker, radius-aware shared grid
  requests, provider diagnostics, persisted lifecycle updates, bounded trails, stale-data guards,
  and restart-safe notification-intent deduplication.
- Added encrypted PushManager subscription registration, VAPID delivery, test notifications,
  quiet hours, cooldowns, bounded retries, permanent failure cleanup, origin checks, and a
  profile-scoped server-sent-events dashboard stream.
- Added tap-to-place and coordinate map onboarding, live aircraft/radius visualization, editable
  location direction/distance/quiet-hour settings, safe location removal, automatic retention,
  SQLite cascade enforcement, and a coordinate-redacted administrator console.
- Added Alembic baseline migration support and corrected Docker Python package installation order.
- Added accessible React onboarding/dashboard shell, PWA worker, Docker Compose, and CI.
- Documented the inherited Home Assistant audit and current incomplete production features.
