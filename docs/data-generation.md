# Data generation

`marketplace_learning_to_rank data generate --seed 42` creates coherent fictional professional profiles, structured unique search requests, full eligible-universe labels, a deterministic query split, a provider-ID cold-start holdout, and a manifest. The CLI defaults to 2,400 providers and 2,400 queries; generator arguments can tune size, categories, regions, candidate top K, cold-start share, and label noise.

Provider rates vary by category and experience with overlap and exceptions. Project count and reviews correlate imperfectly with experience. A portion of complete profiles have no reviews or projects. Availability, location, and remote/on-site delivery are varied separately. All dates are fixed relative to a deterministic reference date so logical rows reproduce for identical inputs.

Queries are unique before splitting. Query IDs, not provider-query rows, are partitioned, and queries with the same category, specialty, and skill intent stay in one partition. The target 70/15/15 ratios are approximate because these intent groups are indivisible. Provider IDs in the cold-start holdout are removed from every training and validation group but remain judged for test analysis. For every request, judgments cover its eligible universe; this lets evaluation count relevant providers missed by retrieval.

The specialty sampler intentionally includes a long tail (machine learning, cybersecurity, UX research, bookkeeping, and paid acquisition are sampled less often) so sparse-specialty slices exist.

All identities, labels, and preference profiles are synthetic. The manifest's creation timestamp changes across runs; generated logical records do not.
