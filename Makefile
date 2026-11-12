.PHONY: setup bootstrap dev train evaluate benchmark test lint typecheck build
setup:
	uv sync --directory apps/api --extra semantic --extra test
	cd apps/web && pnpm install --frozen-lockfile
bootstrap:
	uv run --directory apps/api marketplace_learning_to_rank pipeline run

dev:
	uv run --directory apps/api uvicorn marketplace_learning_to_rank.api.app:app --reload --port 8000 & cd apps/web && pnpm dev
train:
	uv run --directory apps/api marketplace_learning_to_rank train
evaluate:
	uv run --directory apps/api marketplace_learning_to_rank evaluate
benchmark:
	uv run --directory apps/api marketplace_learning_to_rank benchmark
test:
	uv run --directory apps/api pytest
lint:
	uv run --directory apps/api ruff check src tests
	cd apps/web && pnpm lint
typecheck:
	uv run --directory apps/api mypy src/marketplace_learning_to_rank/core/models.py src/marketplace_learning_to_rank/ranking/features.py
	cd apps/web && pnpm typecheck
build:
	cd apps/web && pnpm build
