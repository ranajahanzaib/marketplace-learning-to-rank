# Training

`marketplace_learning_to_rank train` fits LightGBM `LGBMRanker(objective="lambdarank")` with gain `[0,1,3,7,15]`, fixed seed 42, 300 maximum estimators, learning rate 0.04, 15 leaves, depth 5, and validation early stopping. Each query's candidate rows are contiguous, and group sizes are checked against row counts.

Whole query IDs are assigned to train, validation, or test deterministically. The model sees train and validation labels only. In addition, a deterministic 15% provider-ID holdout is removed from both train and validation rows, then examined separately at evaluation time. Validation is used for early stopping; test is reserved for final evaluation.

Training writes native `ranker.txt`, `feature_schema.json`, `model_manifest.json`, and `training_metrics.json`. The manifest records feature names/version, model/dependency identifiers, data version, row and query counts, hyperparameters, training time, and model SHA-256. Serving rejects a feature schema, artifact hash, feature count, or embedding provenance mismatch. CI's opt-in hashing encoder is solely a non-semantic fixture for exercising actual LightGBM training and inference without model download.

The end-to-end CI job sets `RANKLIFT_CI_SMOKE=1` so the API loads the matching fixture encoder and trained fixture model while exercising the browser journey. This opt-in mode exists for test coverage only; it is not a semantic model and must not be used to represent production relevance.
