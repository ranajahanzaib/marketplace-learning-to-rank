# API

Run `uv run --directory apps/api uvicorn marketplace_learning_to_rank.api.app:app --reload --port 8000`. Open `/docs` for generated OpenAPI. Public search is `POST /api/v1/search`; side-by-side ranking is `POST /api/v1/search/compare`. The API also exposes provider details/pair comparison, readiness, demo queries, evaluation reports/failures/segments/cold start, model/schema/importance metadata, pipeline status, and experiment configuration/assignment/event/simulation/result routes.

Requests use Pydantic v2 validation and bounded numeric/text fields. CORS permits only `localhost:5173` and `127.0.0.1:5173` by default. Error responses do not include tracebacks or internal paths. A public service needs access control and rate limiting on experiment and evaluation administration routes.
