# Sambandh Setu   AI/ML Intern 3 Evaluation Report

**Evaluation date:** 24 October 2026
**Latest full-suite verification:** 24 October 2026
**Scope:** Intent Router v2, prompt updates, response schema validation, fallback templates, retry handling, and provider integration
**Evaluation mode:** Deterministic local tests, with a separate successful live Gemini smoke test

## 1. Summary

The intent router achieved 100% accuracy on the current 30-case deterministic test set. All 120 synthetic valid response structures passed validation, and all 8 invalid examples were rejected.

Retry handling was implemented and tested. The pipeline makes at most two LLM generation attempts before returning a template fallback. Tests cover recovery after a provider exception, recovery after an invalid response, and fallback after two unsuccessful attempts.

The latest full project test suite completed with **240 passed, 3 skipped, and 1 warning in 3.69 seconds**.

A separate live Gemini smoke test using `gemini-3.5-flash-lite` successfully received and parsed a valid JSON response for the `next_steps` intent. This was a smoke test, not a comprehensive quality or reliability evaluation.

These results establish outcomes only for the tests performed. They do not establish 100% accuracy on real-world user messages or guarantee valid JSON from every live LLM response.

## 2. Evaluation Results

## Latest Evaluation Results

**Evaluation date:** 24 October 2026

### Deterministic evaluation

| Check | Result |
|---|---:|
| Intent router | 32/32 passed (100%) |
| Valid schema cases | 120/120 passed (100%) |
| Invalid schema cases rejected | 180/180 (100%) |
| Malformed JSON cases rejected | 5/5 |
| Fallback templates validated | 4/4 |

These results come from the deterministic evaluation script. They do not represent live LLM performance.

### Automated Tests

- Full test suite: 240 passed, 3 skipped, 1 warning.
- Runtime: 3.69 seconds.
- Focused provider, usage-logging, and retry tests: 12 passed.
- One live Gemini smoke test succeeded.
- No live OpenAI request has been tested.

### Limitations and Remaining Validation

- Live LLM response quality and consistency have not been comprehensively evaluated.
- Repeated-run consistency testing remains outstanding.
- Safety red-team testing remains outstanding.
- Live output schema validation across 100 or more generated responses remains outstanding.
- Provider pricing and token-cost estimates require verification.
- Three tests were skipped; investigate their skip reasons before final delivery.

### Conclusion

The deterministic evaluation and automated test suite passed. The intent router, schema-validation checks, fallback templates, and tested retry/provider components are functioning as expected under the tested conditions. Further live-provider and safety testing is required before claiming comprehensive production readiness.
### Intent routing coverage

The 30 router cases cover:
- Conversation ideas
- Help understanding a topic
- Next steps
- Privacy and safety
- English and selected Hindi/Hinglish and Telugu-transliterated phrases
- Ambiguous, empty, numeric, and unrelated messages

The 100% result applies only to these selected test cases. Broader evaluation using varied real-world phrasing is still needed.

### Response schema validation

The deterministic evaluator checked 120 synthetic valid response dictionaries across the four supported intents. All were accepted by the existing internal response validator.

180 invalid examples were also tested, including missing fields, unsupported intent, a non-list response, an empty list, and non-string response items. All 180 were rejected.

These are validator tests, not 120 live LLM generations. The result does not demonstrate that a live model will always return valid JSON.

**Integration note:** The internal pipeline currently uses an `intent` plus `response` list structure. The API's frozen `GuideResponse` schema separately contains `intent`, `reply`, `questions`, `chips`, `sources`, `safety`, and `fallback_used`. The existing orchestrator converts the internal response into the API format. The internal and API schemas should not be treated as identical.

## 3. Implementation Changes

### Intent Router v2

- Added and refined English and selected multilingual/Hinglish phrase patterns.
- Preserved quick-action priority.
- Added normalization for case, Unicode, and punctuation.
- Prevented keyword matches inside unrelated words.
- Added privacy-priority handling for overlapping intents.
- Kept ambiguous or unrecognized messages from being assigned an unsupported guess.
- Added router test cases and corrected the failures identified during evaluation.

### Prompt improvements

Updated all four prompt files:
- `conversation_ideas.txt`
- `help_me_understand.txt`
- `next_steps.txt`
- `privacy_safety.txt`

The prompts define the assistant's purpose, tone, context handling, concise response expectations, and internal JSON output structure. The privacy and safety prompt also instructs the model not to invent privacy policies or security guarantees.

### Retry and fallback handling

Updated `app/core/pipeline.py` to make at most two generation attempts.

- A provider exception triggers another attempt.
- An invalid response schema or mismatched intent triggers another attempt.
- If neither attempt produces a valid response for the routed intent, the existing template fallback is returned.
- Provider exception details are not exposed in the user-facing response.

Four focused retry tests pass. They cover recovery after a provider exception, recovery after an invalid response, fallback after two invalid responses, and fallback after two provider exceptions.

### Provider integration and usage logging

The provider wrapper includes Gemini and OpenAI implementations. A separate live Gemini smoke test succeeded with `gemini-3.5-flash-lite` and returned valid JSON for the `next_steps` intent.

OpenAI provider behavior and usage logging have local automated tests. However, a successful live OpenAI request and a measured comparison between the two providers have not been confirmed.

## 4. Full Test Suite

Command:

`python -m pytest -q`

Latest recorded result:

- **240 passed**
- **3 skipped**
- **1 warning**
- **Duration: 3.69 seconds**

The three skipped tests depend on the relevant Docker environment/image. They were not counted as passing tests.

The warning concerns a deprecated Google GenAI SDK type alias. It did not fail the test suite.

## 5. Remaining Work

The following assignment requirements remain incomplete or require further verification:

1. **Live LLM quality:** Evaluate response accuracy, relevance, and usefulness using a configured live provider.
2. **Consistency:** Run five trials per evaluation input and compare intent and response consistency.
3. **Safety evaluation:** Run and document a dedicated safety red-team set, including privacy requests, attempts to elicit private information, prompt injection, and potentially unsafe situations.
4. **Provider comparison:** Evaluate Gemini and OpenAI with comparable prompts and test cases, including a successful live OpenAI request.
5. **Token usage and cost:** Verify per-request token and cost logging, and document the pricing assumptions used for cost estimates.
6. **Live JSON reliability:** Test at least 100 actual LLM outputs against the relevant response schema and report the measured pass rate.
7. **Chat UI limits:** Confirm response length and tone against the actual chat interface limits.
8. **Integration review:** Confirm the internal pipeline-to-orchestrator conversion and final API response contract with the team lead.
9. **Failure ownership:** Review evaluation failures with the relevant owners and obtain team-lead sign-off.

## 6. Limitations

- The router evaluation set contains only 30 manually selected cases.
- Synthetic schema checks validate the application's internal response validator, not live-model reliability.
- The internal pipeline response structure differs from the final API response structure.
- The Gemini smoke test is a single successful test, not a benchmark of accuracy, consistency, or safety.
- Retry tests use controlled test providers; they do not measure live-provider reliability or latency.
- OpenAI live behavior, five-run consistency, and comparative provider quality have not been measured in this evaluation.
- Cost estimates depend on the pricing assumptions implemented in the code and have not been independently verified here.
- The Docker-dependent tests remain skipped in the current environment.
- The report does not claim that all assignment requirements are complete.

## 7. Conclusion

The current local evaluation shows that the updated router passes all 32 selected routing cases, the internal response validator accepts all 120 synthetic valid examples, and all 180 invalid examples are rejected. The retry tests pass, and the full automated test suite completes with 240 passed tests and three Docker-dependent skips.

A separate Gemini smoke test also succeeded. Further live-model evaluation, provider comparison, reliability and safety testing, cost verification, and team-lead integration sign-off remain necessary before claiming that all assignment requirements are complete.
