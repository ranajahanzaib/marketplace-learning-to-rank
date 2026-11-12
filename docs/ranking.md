# Ranking strategies

Eligibility is applied first; it is never represented as a score. Category and `active` are always required. Budget, availability, location, experience, remote delivery, and on-site delivery are hard filters only when the request marks them mandatory. Remote preference is a soft signal.

All strategies operate over the same stable de-duplicated union: top K TF-IDF, top K dense cosine (only when the local model is available), and top K rule scores. Provider ID breaks ties. K comes from the dataset manifest (`candidate_count`).

The rules baseline uses fixed weights: specialty overlap 0.22, skill overlap 0.22, dense semantic cosine 0.11, budget fit 0.12, experience fit 0.10, availability 0.07, location 0.05, remote-preference match 0.04, reliability 0.07. These defaults are documented rather than tuned on test data. The semantic baseline orders by dense cosine only. LambdaMART uses the versioned feature vector and uncalibrated LightGBM scores.
