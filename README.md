# AirSpace

AirSpace is a friendly, self-hosted flight tracker. Choose a spot and a radius, watch nearby
aircraft on a live radar-style map, and receive browser notifications when something enters your
airspace.

- Live aircraft map with plane and helicopter markers
- Browser push notifications—no email service required
- Aircraft details, photos, routes, and Flightradar24 links
- Private, anonymous browser profiles with no accounts or passwords
- Responsive PWA for desktop, Android, iPhone, and iPad
- Multi-architecture Docker images for AMD64 and ARM64

> AirSpace uses unofficial FlightRadar24 endpoints. They may occasionally change, throttle, or
> become unavailable.

## Portainer stack

The easiest deployment is a Portainer **Git repository stack**:

1. In Portainer, open **Stacks** and choose **Add stack**.
2. Select **Repository**.
3. Use `https://github.com/huntrw6/airspace.git` as the repository URL.
4. Set the compose path to `docker-compose.yml`.
5. Add the environment variables below, then deploy the stack.

```env
AIRSPACE_PUBLIC_URL=https://planes.example.com
AIRSPACE_COOKIE_SECURE=true
AIRSPACE_ADMIN_PASSWORD=replace-with-a-long-random-password
AIRSPACE_VAPID_SUBJECT=mailto:admin@example.com
AIRSPACE_TRUSTED_PROXY_HOPS=1
```

The included [Docker Compose file](docker-compose.yml) exposes AirSpace on port `7373` and keeps its
database, notification keys, and anonymous sessions in a persistent Docker volume. VAPID keys and
the session pepper are generated automatically on first startup.

The compose file uses `ghcr.io/huntrw6/airspace:latest` by default. To use Docker Hub, add:

```env
AIRSPACE_IMAGE=huntrw6/airspace:latest
```

Prefer Portainer's web editor? Copy the contents of [docker-compose.yml](docker-compose.yml) into a
new **Web editor** stack and use the same environment variables.

## Docker Compose

```bash
git clone https://github.com/huntrw6/airspace.git
cd airspace
cp .env.example .env
# Edit .env before exposing the app publicly.
docker compose up -d
```

Open `http://SERVER-IP:7373` for a local test.

## HTTPS and notifications

Use an HTTPS reverse proxy for public access and set `AIRSPACE_PUBLIC_URL` to that exact public URL.
Browser notifications and device location require a secure HTTPS context. If one reverse proxy is
in front of AirSpace, use `AIRSPACE_TRUSTED_PROXY_HOPS=1`; otherwise leave it at `0`.

On iPhone or iPad, open AirSpace in Safari, choose **Share → Add to Home Screen**, open the installed
web app, and then enable notifications. Avoid private/incognito mode because the browser may discard
the anonymous profile and push subscription.

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

## License and attribution

AirSpace is MIT licensed. See [LICENSE](LICENSE) for upstream attribution and license details.
