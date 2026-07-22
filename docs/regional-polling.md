# Regional polling

Active locations are assigned to every deterministic 0.25-degree grid cell intersected by their
configured radius. One provider request is planned per occupied cell per cycle, so overlapping
locations share requests, including at cell boundaries. Results from adjacent cells are deduplicated
by normalized flight identity, keeping the newest observation. The strategy is intentionally simple
and testable. `max_regions_per_cycle` bounds request volume when users are widely distributed;
the worker rotates its sorted starting point each cycle so deferred cells are serviced fairly.
Cell merging and adapter-specific maximum bounds remain future optimizations.
