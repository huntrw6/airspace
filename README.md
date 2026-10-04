# AirSpace

[![Star](https://img.shields.io/github/stars/huntrw6/airspace?style=flat&label=%E2%98%86%20Star&labelColor=555&color=yellow)](https://github.com/huntrw6/airspace)
[![Follow](https://img.shields.io/github/followers/huntrw6?style=flat&label=%E2%99%A1%20Follow&labelColor=555&color=red)](https://github.com/huntrw6)
[![Container](https://img.shields.io/badge/%F0%9F%93%A6%20Container-Published-brightgreen?style=flat)](https://github.com/huntrw6/airspace/actions/workflows/publish-container.yml)
[![Image](https://img.shields.io/badge/Image-1f6feb?style=flat&logo=docker&logoColor=white)]([https://github.com/huntrw6/airspace/pkgs/container/airspace](https://hub.docker.com/r/huntrw6/airspace))

**AirSpace is a friendly, self-hosted flight tracker. Choose a radius & watch nearby aircraft on<br>a live radar-style map, receiving browser notifications when something enters Your AirSpace.**

<br>
<p align="center">
  <img src=".github/images/airplane-landing.png" alt="Airplane landing over Los Angeles" width="100%"><br>
  <sub>Photo credit: Danté Vincent</sub>
</p>
<br><br>

- Responsive Progressive Web App for desktop, Android, iPhone, and iPad
- Live aircraft map with markers for planes and helicopters
- Browser push notifications—no text or email service required
- Aircraft details, photos, routes, and links to Flightradar24
- Private, anonymous browser profiles with no accounts or passwords
- Multi-architecture Docker images for AMD64 and ARM64

<br>

> AirSpace uses FlightRadar24 endpoints that may occasionally change, throttle, or
> become unavailable.

<br>

## Portainer stack

In Portainer, choose **Stacks → Add stack → Web editor**. Open the Compose file below, copy it into
the editor, and update the public URL, administrator password, VAPID email, and proxy settings for
your deployment. Then select **Deploy the stack**.

<details>
<summary><strong>Open the complete docker-compose.yml</strong></summary>

```yaml
services:
  airspace:
    container_name: airspace
    image: ${AIRSPACE_IMAGE:-ghcr.io/huntrw6/airspace:latest}
    restart: unless-stopped
    environment:
      AIRSPACE_ENVIRONMENT: production
      AIRSPACE_DATABASE_URL: sqlite:////app/data/airspace.db
      AIRSPACE_PUBLIC_URL: ${AIRSPACE_PUBLIC_URL:-http://localhost:7373}
      AIRSPACE_COOKIE_SECURE: ${AIRSPACE_COOKIE_SECURE:-false}
      AIRSPACE_ADMIN_PASSWORD: ${AIRSPACE_ADMIN_PASSWORD:-ReplaceThisWithSecretAdminPassword}
      AIRSPACE_SESSION_PEPPER: ${AIRSPACE_SESSION_PEPPER:-}
      AIRSPACE_PROVIDER_ENABLED: ${AIRSPACE_PROVIDER_ENABLED:-true}
      AIRSPACE_POLL_INTERVAL_SECONDS: ${AIRSPACE_POLL_INTERVAL_SECONDS:-20}
      AIRSPACE_PROVIDER_DETAIL_REQUESTS_PER_CYCLE: ${AIRSPACE_PROVIDER_DETAIL_REQUESTS_PER_CYCLE:-3}
      AIRSPACE_PROVIDER_EMPTY_CYCLES_BEFORE_RESET: ${AIRSPACE_PROVIDER_EMPTY_CYCLES_BEFORE_RESET:-3}
      AIRSPACE_TRUSTED_PROXY_HOPS: ${AIRSPACE_TRUSTED_PROXY_HOPS:-0}
      AIRSPACE_GEOCODING_USER_AGENT: ${AIRSPACE_GEOCODING_USER_AGENT:-AirSpace/0.1 (self-hosted)}
      AIRSPACE_AIRCRAFT_PHOTOS_ENABLED: ${AIRSPACE_AIRCRAFT_PHOTOS_ENABLED:-true}
      AIRSPACE_VAPID_PUBLIC_KEY: ${AIRSPACE_VAPID_PUBLIC_KEY:-}
      AIRSPACE_VAPID_PRIVATE_KEY: ${AIRSPACE_VAPID_PRIVATE_KEY:-}
      AIRSPACE_VAPID_SUBJECT: ${AIRSPACE_VAPID_SUBJECT:-mailto:admin@example.com}
    ports:
      - "${AIRSPACE_PORT:-7373}:7373"
    volumes:
      - airspace-data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7373/health/ready',timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s

volumes:
  airspace-data:
```

</details>

The stack exposes AirSpace on port `7373` and stores its database, notification keys, and anonymous
sessions in the persistent `airspace-data` volume. VAPID keys and the session pepper are generated
automatically on first startup. To pull from Docker Hub instead of GHCR, replace the image line with
`image: huntrw6/airspace:latest`.

<br>

## Docker Compose

```bash
git clone https://github.com/huntrw6/airspace.git
cd airspace
cp .env.example .env
# Edit .env before exposing the app publicly.
docker compose up -d
```

Open `http://SERVER-IP:7373` for a local test.

<br>

## HTTPS and notifications

Use an HTTPS reverse proxy for public access and set `AIRSPACE_PUBLIC_URL` to that exact public URL.
Browser notifications and device location require a secure HTTPS context. If one reverse proxy is
in front of AirSpace, use `AIRSPACE_TRUSTED_PROXY_HOPS=1`; otherwise leave it at `0`.

On iPhone or iPad, open AirSpace in Safari, choose **Share → Add to Home Screen**, open the installed
web app, and then enable notifications. Avoid private/incognito mode because the browser may discard
the anonymous profile and push subscription.

<br>

## Updating and troubleshooting

In Portainer, pull and redeploy the stack. With Docker Compose:

```bash
docker compose pull
docker compose up -d
```

Useful checks:

```bash
docker compose ps
docker compose logs -f --tail=200 airspace
curl http://localhost:7373/health/live
curl http://localhost:7373/health/ready
```

Back up the persistent `airspace-data` volume before major updates. Pin `AIRSPACE_IMAGE` to a
version or image digest when a deployment should not automatically follow `latest`.

<br>

## CARTO basemap key

The flight map and location picker use CARTO's dark raster basemap. Register for a
basemap key at https://carto.com/basemaps/apikey to remove the "API key required"
watermark.

For images published by this repository's GitHub Actions workflow, set the repository
Actions secret `CARTO_BASEMAPS_API_KEY`, then publish a new image and pull/redeploy it
in Portainer. The same key is included in both GHCR and Docker Hub builds.

For a local image build:

```bash
read -r -s -p "CARTO basemap key: " VITE_CARTO_BASEMAPS_API_KEY
export VITE_CARTO_BASEMAPS_API_KEY
docker build --build-arg VITE_CARTO_BASEMAPS_API_KEY -t airspace:local .
unset VITE_CARTO_BASEMAPS_API_KEY
```

For frontend development, put `VITE_CARTO_BASEMAPS_API_KEY=your-key` in
`frontend/.env.local` before starting Vite. This is a **build-time, client-side**
key: setting it only in a running container's environment will not update the map.
It is visible in browser tile requests and the built JavaScript, so use a dedicated
basemap key, not a private backend credential. After updating, force-refresh the
browser or close and reopen the installed PWA to clear old map tiles.

<br>

## Development

```bash
python -m venv .venv
.venv/Scripts/pip install -e "./backend[dev]"  # Use .venv/bin/pip on Linux/macOS
pytest backend/tests
cd frontend
npm install
npm run lint && npm run build && npm test
```

More detail is available in [the project documentation](docs/architecture.md), including
[deployment](docs/docker-deployment.md), [privacy](docs/privacy.md),
[security](docs/security.md), and [notifications](docs/notifications.md).

