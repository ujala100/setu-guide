# AI/ML Intern 1 — Targeted Router Improvement

Date: 2026-10-26

## Objective
Use the v2 evaluation failures to make a small, evidence-led improvement to the existing intent router. This is within AI/ML Intern 1 scope (data, scenarios and evaluation); no new product feature was added.

## Baseline
Before changes, 109 of 128 scenarios matched their expected intent (85.2%). Nineteen cases failed across three repeated message patterns:
- “Suggest some questions about hobbies.” was not recognized as `conversation_ideas`.
- “Suggest a next step for our conversation.” was incorrectly captured by the broad `conversation` keyword and routed to `conversation_ideas`.
- “What should I avoid sharing?” was not recognized as `privacy_safety`.

See `eval/results/baseline_v2.json` for the recorded baseline metrics and failure examples.

## Changes made
- Reordered router rules so specific next-step phrases are checked before broad conversation wording.
- Added missing hobby-question and privacy/disclosure phrases.
- Normalized whitespace and used `casefold()` for case-insensitive matching.
- Kept supported quick-action priority and unknown-message fallback behavior.
- Added three regression tests for the previously failing patterns.

## Latest evaluation
The one-command evaluation (`python eval/run_eval.py`) now reports:

| Metric | Before | After |
|---|---:|---:|
| Intent accuracy | 85.2% | 100.0% |
| Relevance proxy (intent match) | 85.2% | 100.0% |
| Five-run router consistency | 100.0% | 100.0% |
| Red-team flag detection | 100.0% | 100.0% |
| Edge-case crash-free rate | 100.0% | 100.0% |

The after results are saved in `eval/results/latest_v2.json`. The 100% accuracy is on this current 128-scenario set; it is not a guarantee of production accuracy and the set should be reviewed for duplicates and held-out coverage. “Relevance” is only an intent-match proxy, not a human quality score. The red-team metric measures expected input-flag detection, not full end-to-end response safety. Consistency tests deterministic routing, not generated LLM replies.

## Verification limitation
The repository-wide pytest suite still cannot collect in this environment because `google.genai` is unavailable to `app/core/llm_provider.py`. Therefore the full existing test suite is **not verified as passing**. The evaluation script itself ran successfully. Install the repository's intended dependencies and rerun pytest before sign-off.

## Next high-value actions
1. Install dependencies from the repository's declared dependency file and run the full tests.
2. Add genuinely held-out and less templated scenarios to reduce overfitting risk.
3. Test complete responses for privacy leakage and safety, not only input flags.
4. Review intent labels and expected outcomes with the team lead before treating these scores as release gates.
