# AirSpace

AirSpace is a private-by-design web app that tells ordinary people which aircraft are near a
chosen home or viewing spot. It runs independently of Home Assistant and supports multiple
anonymous browser profiles, each with private locations and preferences.

> Early standalone release: profile/location APIs, onboarding PWA, persistence, geographic
> filtering, shared regional polling, persisted tracking, health/admin boundaries, Docker
> packaging, encrypted Web Push delivery, and automated tests are implemented. See **Current
> limitations** for the remaining production work.

## Docker quick start

```bash
git clone https://github.com/huntrw6/airspace.git
cd airspace
cp .env.example .env
# Replace the default AIRSPACE_ADMIN_PASSWORD before public deployment.
docker compose up -d
```

Open `http://SERVER:7373`. For public use, put AirSpace behind an HTTPS reverse proxy and set
`AIRSPACE_PUBLIC_URL` to its URL. Secure browser notifications and installable-PWA behavior require
HTTPS (localhost is the development exception).

AirSpace automatically generates its browser-push VAPID key pair on first startup and stores it in
the persistent data volume. Set the VAPID subject to a monitored administrator address. To use a
manually managed pair instead, set both key variables before startup:

```bash
docker compose run --rm airspace python -m airspace.generate_vapid
```

The container also generates `/app/data/session-pepper` on first startup and reuses it from the
persistent volume. Do not delete or replace that file unless invalidating all anonymous sessions is
intentional. The bundled administrator password is only a deployment placeholder. It allows the
stack to start, but should be replaced before exposing `/admin` publicly.

Images for `linux/amd64` and `linux/arm64` are published from `main` to
`ghcr.io/huntrw6/airspace:latest` and, when the Docker Hub repository secrets are configured,
`huntrw6/airspace:latest`. Version tags such as `v1.2.3` also publish immutable versioned images.
Set `AIRSPACE_IMAGE` to a version or digest when a deployment must not track `latest`.

## Anonymous profiles

There is no registration screen, username, email, recovery code, or cross-device linking. AirSpace
sets a long random credential in a Secure, HttpOnly, SameSite cookie and stores only its keyed hash.
Database IDs, coordinates, device IDs, and push endpoints are never credentials. Clearing browser
data or deleting the installed PWA can permanently remove access; create a new profile on another
device. Users can delete locations or their whole profile.

## Browsers and iPhone installation

Current Chrome, Edge, Firefox, and Safari releases can use the live dashboard. Web Push support
depends on the browser and operating system. On iPhone and iPad, open AirSpace in Safari, tap Share,
choose **Add to Home Screen**, open the installed AirSpace icon, and then enable notifications. The
onboarding flow detects this case and shows installation guidance before requesting permission.
Private/incognito browsing is unsuitable because the anonymous profile and push subscription may be
discarded when the session closes.

## Reverse proxy (Nginx Proxy Manager)

Create a Proxy Host to `http://airspace:7373` (or the Docker host and exposed port), enable WebSocket
support, request a Let's Encrypt certificate, and enable Force SSL. Do not publish the container
without TLS. Preserve the original client IP only from trusted proxy addresses; use network-level
access controls for `/api/admin` in addition to the administrator credential.

## Back up, restore, update, and roll back

```bash
# Backup while stopped for a consistent SQLite copy
docker compose stop airspace
docker run --rm -v airspace_airspace-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/airspace-data.tgz -C /data .
docker compose start airspace

# Restore into an empty/replacement volume
docker compose down
docker run --rm -v airspace_airspace-data:/data -v "$PWD":/backup alpine \
  sh -c 'rm -f /data/* && tar xzf /backup/airspace-data.tgz -C /data'
docker compose up -d

# Upgrade (back up first)
git pull --ff-only
docker compose pull
docker compose up -d

# Roll back the image, then restore the matching backup if a migration changed data
AIRSPACE_IMAGE=ghcr.io/huntrw6/airspace:<known-good-tag> docker compose up -d
```

The example configuration sets `AIRSPACE_TRUSTED_PROXY_HOPS=1` for the single reverse-proxy
topology described here. Set it to `0` if AirSpace is directly exposed, and match the exact proxy
hop count in more complex deployments; otherwise forwarded client addresses are intentionally
ignored to prevent header spoofing.

Inspect with `docker compose ps`, `docker compose logs -f --tail=200 airspace`,
`curl http://localhost:7373/health/live`, and `curl http://localhost:7373/health/ready`.

## Local development and tests

```bash
python -m venv .venv
.venv/Scripts/pip install -e "./backend[dev]"  # use .venv/bin/pip on Linux/macOS
pytest backend/tests
cd frontend && npm install && npm run lint && npm run build && npm test
```

## Design documentation

- [Audit](docs/audit.md)
- [Architecture](docs/architecture.md)
- [Provider behavior](docs/provider-behavior.md)
- [Regional polling](docs/regional-polling.md)
- [Anonymous profiles](docs/anonymous-profiles.md)
- [Notifications](docs/notifications.md)
- [Privacy](docs/privacy.md)
- [Security](docs/security.md)
- [Docker deployment](docs/docker-deployment.md)
- [Migration from Home Assistant](docs/migration-from-home-assistant.md)

## Current limitations

- The unofficial FlightRadar24 adapter and background worker are connected when
  `AIRSPACE_PROVIDER_ENABLED=true`. These undocumented endpoints may change or reject a deployment;
  live-provider behavior could not be exercised in this development environment, so health and
  degraded-state diagnostics must be checked after deployment.
- VAPID Web Push, browser subscription registration, test notifications, quiet hours, cooldowns,
  retry limits, and invalid-subscription cleanup are connected. They still require real VAPID keys,
  HTTPS, and verification against target browsers after deployment.
- Device geolocation, coordinate entry, tap-to-place selection, and server-proxied address search
  are implemented. Address search text is disclosed to the configured geocoder (Nominatim by
  default); results are cached and outbound requests are limited to one per second.
- Alembic applies the versioned baseline automatically at startup and is checked in CI.
- `/admin` provides a protected operational summary and manual retention cleanup. It is intentionally
  compact. Global limits remain environment-controlled so a compromised browser session cannot
  silently change operational or retention policy; their effective values are visible in `/admin`.

These are functional gaps, not hidden placeholders. The app remains available during provider
failure, retains its last sightings, marks missing aircraft held/historic only after successful
polls, and refuses to create sightings or notification intents from stale observations.

## License and attribution

MIT licensed. The original copyright notice for `8bither0/whats-that-plane` is preserved in
`LICENSE`. The legacy integration, screenshots, directional-FOV idea, and related presentation were
derived from that project. New standalone code is not attributed to the upstream author. Leaflet's
bundled legacy distribution carries its own BSD-2-Clause header; it is excluded from the production
image. Map deployments must preserve OpenStreetMap/CARTO attribution if those tile services are used.
