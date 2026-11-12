# Architecture

The API package separates domain schemas, generated data, validation, embedding/index build, retrieval, feature calculation, ranking, training, evaluation, experimentation, and HTTP transport. The FastAPI lifespan builds the local TF-IDF matrix once, loads a validated LightGBM native model when available, and uses a checked dense provider matrix artifact. Each search applies hard constraints, forms a lexical/dense/rules candidate union, then scores that same pool.

Generated providers and judgments are JSON for an inspectable local demo. Dense embeddings are normalized NumPy NPZ arrays with JSON metadata. Training features are JSONL. Model artifacts use LightGBM's native text format and are accompanied by a feature schema, manifest, hash, and training metrics. SQLite stores experiment definitions, persistent assignments, and idempotent events.

A larger catalog could replace the in-memory TF-IDF and dense matrix with a persisted inverted index and approximate nearest-neighbor search. That scaling path is future work; no vector database or search cluster is required for the local catalog.
