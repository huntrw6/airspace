# Provider behavior

`FlightProvider` is the only business-layer contract. It returns `NormalizedFlight` values and
supports region fetch, details, health, and feature discovery. Provider-specific dictionaries are
parsed record-by-record; malformed records raise `ProviderError` without requiring callers to drop
the whole response. Unknown altitude remains `None`. Network implementations must use timeouts,
bounded exponential backoff with jitter, respect rate limits, and cache successful details with a
TTL while retrying failures later. FlightRadar24 access is unofficial and may change or stop; no
access control or anti-bot mechanism may be bypassed.

Rate-limited requests fail immediately instead of being amplified by retries. The adapter honors a
bounded `Retry-After` cooldown independently for the position and detail hosts. Detail enrichment
is limited to `AIRSPACE_PROVIDER_DETAIL_REQUESTS_PER_CYCLE` new lookups per polling cycle (three by
default); cached details do not consume that budget, and regional positions remain the priority.

The current `FlightRadar24Provider` uses the public regional feed and click-handler endpoints
behind that contract. Both are undocumented and may change without notice. Positional feed arrays
are decoded in one parser, malformed aircraft are skipped individually, successful detail results
have a bounded TTL, and failed details are not cached. HTTP 429 and upstream failures use bounded
retry/backoff; diagnostics store error categories rather than payloads or viewing locations.

Regional requests explicitly include every airborne reception class exposed by the
FlightRadarAPI tracker configuration: ADS-B, MLAT, FAA, satellite, FLARM, gliders, and estimated
positions. Ground targets and airport vehicles remain disabled because they are not useful for
overhead-aircraft notifications. FlightRadarAPI itself wraps the same FlightRadar24 feed and
click-handler endpoints, so calling it alongside this adapter would duplicate upstream traffic
without creating an independent fallback.
