# Feature engineering

Feature schema `1.1.0` is declared in `marketplace_learning_to_rank.ranking.features`. It uses one function for training and online-style serving. It includes normalized-text evidence (dense cosine, TF-IDF, token overlap, specialty and skill overlap, category match); budget (rate, requested cap, ratio, distance, within-cap); experience (years, requested gap and fit, satisfaction, projects); availability (state, days to availability, fit); geography and delivery (city/country, remote/on-site compatibility and preference); quality (rating, review count, Bayesian-style shrinkage, confidence, response history/time, verification); and cold-start/missingness flags and provider tenure.

Missing ratings use a neutral value of 3.5 and have a separate `rating_missing` feature. Adjusted rating uses the same 3.5 prior weighted by `n/(n+10)`. Missing response history has its own flag and a neutral zero value; it is not a negative rating. The query timestamp is fixed to the generated reference date so availability/tenure features are deterministic. No label or preference-generator latent variable is used as an inference feature.

LightGBM contribution values explain score contributions for a feature vector. They are not causal effects or explanations of customer choice.
