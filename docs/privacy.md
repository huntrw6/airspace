# Privacy

Exact viewing coordinates, session credentials, push endpoints, and encryption keys are sensitive.
No endpoint enumerates profiles or locations. Logs must never include request cookies, bodies for
location/subscription routes, exact coordinates, endpoints, or keys. AirSpace contains no analytics,
advertising, CAPTCHA, or recovery system. Users can delete individual locations or all profile data.
Retention defaults to 60 days for sightings. An idempotent background job removes expired history,
old permanently invalid subscriptions, and abandoned profiles according to administrator settings.
The administrator console shows aggregate counts and grid-region keys, never exact home coordinates.

When aircraft photos are enabled, the server sends only the public aircraft registration to the
Planespotters.net photo API. A browser displaying a returned thumbnail connects to the
Planespotters.net image host and therefore discloses its IP address to that service. Viewing
coordinates, profile identifiers, and push subscription data are never included in photo requests.
