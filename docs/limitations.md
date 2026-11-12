# Limitations

Providers, requests, relevance labels, preference patterns, and simulated traffic are synthetic. No human judgments or real booking outcomes are included. Dense search requires downloading the local sentence-transformer model; the rules baseline works without it, while semantic and dense-trained model modes are explicitly unavailable without matching embeddings.

Bootstrap intervals measure variation over synthetic held-out queries. Query segments overlap and are not independent experiments. The provider-ID holdout tests generalization inside this generator, not to a real provider population. No production conversion lift, fairness validation, real-event analysis, position-bias correction, propensity correction, online governance, or drift monitoring is established. Do not use for hiring or provider selection without human judgments, legal review, fairness testing, and domain validation.
