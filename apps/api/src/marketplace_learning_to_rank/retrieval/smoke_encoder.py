"""Deterministic hashing encoder for CI only; not a semantic embedding model."""
from sklearn.feature_extraction.text import HashingVectorizer
class SmokeEncoder:
    model_id="marketplace_learning_to_rank-ci-hashing-fixture-v1"
    def __init__(self):self.vectorizer=HashingVectorizer(n_features=384,alternate_sign=False,norm='l2',stop_words='english')
    def encode(self,texts,normalize_embeddings=True,show_progress_bar=False):return self.vectorizer.transform(texts).toarray()
