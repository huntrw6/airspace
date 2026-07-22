# Provider behavior

`FlightProvider` is the only business-layer contract. It returns `NormalizedFlight` values and
supports region fetch, details, health, and feature discovery. Provider-specific dictionaries are
parsed record-by-record; malformed records raise `ProviderError` without requiring callers to drop
the whole response. Unknown altitude remains `None`. Network implementations must use timeouts,
bounded exponential backoff with jitter, respect rate limits, and cache successful details with a
TTL while retrying failures later. FlightRadar24 access is unofficial and may change or stop; no
access control or anti-bot mechanism may be bypassed.

The current `FlightRadar24Provider` uses the public regional feed and click-handler endpoints
behind that contract. Both are undocumented and may change without notice. Positional feed arrays
are decoded in one parser, malformed aircraft are skipped individually, successful detail results
have a bounded TTL, and failed details are not cached. HTTP 429 and upstream failures use bounded
retry/backoff; diagnostics store error categories rather than payloads or viewing locations.
