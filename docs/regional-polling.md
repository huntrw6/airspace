# Regional polling

Active locations are assigned to every deterministic 0.25-degree grid cell intersected by their
configured radius. One provider request is planned per occupied cell per cycle, so overlapping
locations share requests, including at cell boundaries. Results from adjacent cells are deduplicated
by normalized flight identity, keeping the newest observation. The strategy is intentionally simple
and testable. `max_regions_per_cycle` bounds request volume when users are widely distributed;
the worker rotates its sorted starting point each cycle so deferred cells are serviced fairly.
Cell merging and adapter-specific maximum bounds remain future optimizations.

The default provider interval is 20 seconds. Browser dashboards also refresh their persisted
sighting snapshot every 15 seconds as a fallback for a buffered or interrupted event stream; those
fallback requests read AirSpace's database and do not create additional provider traffic. Between
provider observations, the map projects each marker for no longer than the time its reported speed
would take to cross that location's circle. A short missed cycle changes a sighting to `held`, which
remains visible until the normal stale lifecycle moves it into history.
