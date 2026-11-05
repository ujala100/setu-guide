# AI/ML Intern 1 — Data, Scenarios and Evaluation

**Prepared by:** Rohit Vardhan  
**Role:** ML Intern

## Included deliverables

- `data/profiles/profiles_v2.json` — expanded profile examples.
- `data/conversations/scenarios_v2.json` — stage/intent scenario set with expected behaviour.
- `data/conversations/edge_cases_v2.json` — edge-case inputs for robustness checks.
- `data/conversations/red_team_v2.json` — safety and prompt-injection test cases.
- `eval/run_eval.py` — evaluation runner for the included scenario set.
- `tests/test_intent_router.py` — router regression tests.
- `docs/aiml1_initial_audit.md` and `docs/aiml1_router_improvement.md` — audit and implementation notes.
- `docs/reports/Setu_Guide_AIML_Intern1_Report.pdf` and `.docx` — handover report.

## Important validation note

These deliverables are a working baseline, not production sign-off. Run the evaluation and test suite in the project environment, inspect any failures, validate labels against the product's canonical quick-action/stage definitions, and obtain reviewer approval before treating the scores as final. The report records known limitations and the current test-environment dependency issue.

## Suggested commands

```bash
pip install -r requirements-dev.txt
python eval/run_eval.py
pytest -q
```

Run commands from the repository root. Some tests may require dependencies or configuration not available in every environment.
