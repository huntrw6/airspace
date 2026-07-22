# AirSpace legacy audit

## Scope and provenance

The initial workspace contained eight source/configuration files, two bundled Leaflet assets,
three screenshots, a README, and the MIT license. The workspace had no `.git` directory, so
the public repositories were cloned read-only for provenance review. The commit graph of
`huntrw6/airspace` matches `8bither0/whats-that-plane` through commit `72dfd2e`; a content
comparison found no project-file differences. The code and screenshots are therefore inherited.
The original MIT copyright notice is retained in `LICENSE`; new work is described separately.

## Original runtime

1. Home Assistant loads `custom_components/whats_that_plane` and its config flow.
2. A `DataUpdateCoordinator` polls FlightRadarAPI for a bounding box per HA config entry.
3. Each aircraft is filtered by geodesic distance, altitude, bearing, and FOV.
4. A Cloudflare-oriented scraper calls FlightRadar24's undocumented click-handler endpoint once
   when the aircraft first enters view.
5. Mutable provider dictionaries, trails, and history are retained only in process memory.
6. A sensor publishes the entire model as Home Assistant entity attributes.
7. A custom Lovelace element reads that entity, copies bundled Leaflet into HA's public folder,
   and loads CARTO/OpenStreetMap tiles in the browser.

## Dependencies and outbound services

- Home Assistant config entries, coordinator, sensor entities, event bus, and Lovelace resources.
- FlightRadarAPI 1.4.0 (unofficial), cloudscraper 1.2.71, dpath 2.2.0, geopy 2.4.1.
- Undocumented `flightradar24.com` and `data-live.flightradar24.com/clickhandler` requests.
- Bundled Leaflet JavaScript/CSS; header identifies Leaflet's BSD-2-Clause license.
- CARTO Voyager map tiles with OpenStreetMap and CARTO attribution.

## Verified defects

- Every active identifier, documentation link, issue link, code owner, HACS workflow, and UI
  contract still targets the upstream Home Assistant integration; `hacs.json` has a trailing comma.
- Polling is per HA entry. There is no sharing, persistence, user isolation, authentication,
  notification delivery, rate limiting, readiness model, migration system, CI, or Docker service.
- A failed detail lookup becomes `{}` and is never retried while tracked. Details never refresh.
- One outer exception fails the full poll. Provider dictionaries escape into every other layer.
- Unknown altitude/speed become zero. Trails are unbounded. Held flights remain in the returned
  visible list. Historic state disappears on restart.
- Configuration permits zero/negative radius, intervals, hold time, and history counts, and does
  not enforce minimum altitude <= maximum altitude.
- Fractional UTC offsets are truncated; `%-I` is not portable to Windows; fallbacks use local
  naive time. Route progress is a misleading great-circle ratio.
- The map rejects valid zero coordinates/trail points through truthiness tests, redraws broadly,
  changes Leaflet prototype behavior, and does not reliably dispose observers/listeners.
- Provider-controlled values participate in HTML construction and links. URL schemes are not
  allow-listed. Exact viewing coordinates are present in a broadly readable HA entity.

## Legacy disposition

The original integration was removed from the standalone branch. Its provenance remains available
in Git history and the license documentation. Migration guidance explains the one-way recreation
of settings; no Home Assistant database is read.
