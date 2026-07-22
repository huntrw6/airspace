# Architecture and implementation plan

Airspace is a single deployable web application with a FastAPI API, a React/TypeScript PWA, and
SQLite by default. SQLAlchemy models avoid SQLite-specific business logic so PostgreSQL remains a
practical future option. All timestamps are aware UTC values at storage/API boundaries.

## Boundaries

- `providers`: typed provider protocol, normalization, bounded retry/backoff, detail TTL cache,
  and health. Raw provider payloads never leave this boundary.
- `polling`: fixed geographic grid grouping with adjacent-cell merge limits; each region is fetched
  once and aircraft are deduplicated by normalized/provider identity.
- `detection`: pure geographic predicates and deterministic lifecycle transitions.
- `database`: profiles, locations, devices, sightings, deliveries, tracked state, settings, health,
  and polling diagnostics with migrations.
- `auth`: opaque random browser sessions stored as hashes; the raw credential exists only in a
  Secure/HttpOnly/SameSite cookie. Admin authentication is separate.
- `notifications`: persisted, uniquely constrained delivery intents followed by Web Push delivery.
- `api`: profile-scoped REST resources, status/health, admin resources, and server-sent events.
- `retention`: bounded, idempotent cleanup for trails, sightings, invalid devices, and abandoned
  profiles.
- `frontend`: onboarding, location/settings, dashboard, history, notification setup, privacy
  controls, and an admin view. Text is rendered by React; no provider HTML is injected.

## Milestones

1. Foundation: settings, database schema/migration, session/admin auth, health, geographic tests.
2. Provider/polling: provider protocol, FR24 adapter, health, cache/retries, shared grid regions.
3. Tracking: filters, persisted lifecycle, bounded trails/history, stale-data guard, deduplication.
4. Product: accessible mobile onboarding/dashboard/settings with live updates and map fallback.
5. PWA/push: service worker, VAPID subscriptions, deep links, status, test delivery, iOS guidance.
6. Operations: admin diagnostics/limits/retention, privacy deletion, rate limits, redacted logs.
7. Hardening: CI, unit/component/E2E tests, container builds, backup/restore/upgrade documentation.
8. Verification: clean Compose start, two-profile shared-region scenario, restart/outage scenarios.

Schema changes are tracked through Alembic. The baseline revision is intentionally idempotent for
early standalone databases created before migration tracking; future schema changes require explicit
revision files and are applied during application startup before background workers begin.

## Migration

There is no automatic import of Home Assistant state because HA entity attributes are neither a
stable database nor an authentication boundary. Administrators deploy Airspace beside HA, users
recreate locations through onboarding, verify notifications, and then remove the legacy integration.
