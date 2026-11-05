# Setu Guide — AI/ML Intern 1 Rapid Audit and v2 Work Log

## Scope
Aligned to `next tasks.pdf`: synthetic profiles, scenarios, coverage, edge cases, red-team cases, evaluation, baseline, regression and consistency. This is a rapid implementation based on the supplied repository, not a claim that every system-level sign-off criterion is met.

## Initial repository gaps addressed
- Profile and conversation data folders were placeholders; added versioned synthetic profile/scenario sets.
- Existing router tests did not provide a single consolidated evaluation report; added `eval/run_eval.py`.
- Added explicit edge-case and red-team data with expected outcomes.
- Added a targeted regression subset in `tests/regression/`.

## Deliverables added
- `data/profiles/profiles_v2.json`: 60 synthetic profiles, including sparse and mismatched/unusual pair cases.
- `data/conversations/scenarios_v2.json`: 128 cases (8 stages × 4 intents × 4 message variations), each with expected intent and behavior.
- `data/conversations/edge_cases_v2.json`: Hindi/Hinglish, empty/whitespace, emojis, long input, ambiguity, injection, privacy, prediction, decision and distress examples.
- `data/conversations/red_team_v2.json`: 14 red-team cases across injection, private data, relationship outcome predictions, decisions and distress.
- `eval/run_eval.py`: one-command JSON evaluation for intent accuracy, an intent-match relevance proxy, deterministic five-run consistency, red-team detection and edge-case crash rate.
- `eval/results/baseline_v2.json`: generated metrics and per-case details (regenerate after changes).
- `tests/regression/test_ai_ml1_regression.py`: must-pass data integrity, coverage and safety checks.

## Important limitations
- Relevance is only approximated by intent match; human scoring of response quality is still needed.
- Five-run consistency currently covers the deterministic intent router, not stochastic LLM response generation.
- Rule-based intent accuracy may be low for paraphrases/Hindi/Hinglish; report actual values and do not tune against the test set without documenting changes.
- A passing red-team detector test is not equivalent to proving 100% end-to-end safe replies. The whole pipeline and logs must also be tested.
- No real user data is included in generated profiles.

## Commands
From repository root:

```bash
python eval/run_eval.py
python -m pytest tests/regression -q
python -m pytest -q
```

## Severity / next fixes
1. **High:** expand routing coverage for Hinglish and ambiguous messages based on evaluation failures, without breaking quick-action priority.
2. **High:** test safety through the complete API/pipeline, including output checks and log privacy.
3. **Medium:** add human relevance rubric and scorer; current relevance proxy is limited.
4. **Medium:** integrate regression suite into CI only after the team lead approves the workflow change.

## Status
Data/evaluation scaffolding added. Full-suite execution, CI integration, human quality scoring and lead sign-off remain outstanding and must not be represented as completed until verified.
