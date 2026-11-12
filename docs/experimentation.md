# Experimentation

SQLite persists experiment configuration, deterministic visitor assignments, and event IDs. Assignment hashes experiment salt, experiment ID, and visitor ID into a fixed allocation bucket. Event IDs are unique and duplicate writes are idempotent. `results_exposed` is the explicit impression definition; an API search alone is not exposure.

Events include strategy/model provenance, request/provider/position fields, timestamp, and `source` (`simulated` or `real`). The bounded simulator varies customer preference by visitor and click propensity by relevance and rank position. It does not award a strategy a fixed bonus. Reports use the randomized visitor as the unit, calculate exposure counts, click/shortlist/contact/booking-like rates, approximate sample-ratio mismatch, user-cluster bootstrap intervals, and a sample-size planning estimate.

Simulation reports are kept separate from real-source events and prominently labeled synthetic. They test assignment and instrumentation behavior; they do not establish actual customer conversion lift. Public deployments need authentication and abuse protection for experiment configuration and event ingestion.
