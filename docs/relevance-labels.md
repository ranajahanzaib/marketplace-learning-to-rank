# Relevance labels

Labels are integer grades 0–4. The generator combines exact specialty fit, skill overlap, budget suitability, experience, availability, remote-preference match, reliability, and a nonlinear skill/project-history interaction. Four preference mixes change those tradeoffs by query, with controlled random noise. The label formula is not the fixed rules score, but it remains a simulated target and can encode generator assumptions.

Training and evaluation use graded gain `2^label - 1`. Binary precision/recall regard grade 3 or 4 as relevant. A label is not an observed click, human assessment, booking, or proof of marketplace utility.
