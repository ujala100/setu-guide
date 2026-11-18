Sambandh Setu — Gemini Model Comparison (Reduced-Sample Benchmark)
Date: 6 November 2026
Status: Benchmark execution complete; reduced-sample analysis
Purpose: Compare response latency, successful response rate, schema validity, intent matching, and repeated-run consistency for the two Gemini model IDs requested by the team lead.
1. Scope and method
The benchmark used six scenarios from the official Setu Guide dataset:

teammate/data/scenarios-v1:data/scenarios_v1.json
Scenario	Input type	Language	Expected intent
s01	Structured	English	conversation_ideas
s02	Structured	English	help_me_understand
s03	Structured	English	next_steps
s04	Structured	English	privacy_safety
f06	Free text	Hinglish	conversation_ideas
f08	Free text	Hinglish	next_steps


Both models received the same selected scenarios and prompts. Each scenario was run three times per model. The request order alternated between models to reduce systematic ordering bias.
- Models: gemini-3.5-flash-lite and gemini-3.5-flash
- Scenarios: 6
- Repetitions per scenario per model: 3
- Planned and completed requests: 36
- Request timeout passed by the benchmark: 30 seconds
- Delay after successful requests: 12 seconds
- Cooldown after failed requests: 20 seconds
This six-scenario scope and three-repetition setting were approved by the team lead. It is a reduced-sample comparison, not a full evaluation of all 47 scenarios.
2. Results
2.1 Latency and request reliability
Metric	gemini-3.5-flash-lite	gemini-3.5-flash
Total requests	18	18
Successful requests	18	15
Failed requests	0	3
Success rate	100.00%	83.33%
Failure rate	0.00%	16.67%
Valid responses	18	15
Expected-intent matches	18	15
Average latency, all attempts	5.311 s	18.247 s
Average latency, successful attempts only	5.311 s	15.742 s


The three failed gemini-3.5-flash attempts were reported in the terminal as APITimeoutError. The provider returned no response for those attempts. All 18 gemini-3.5-flash-lite attempts succeeded.
2.2 Relative latency
Using successful requests only:
- gemini-3.5-flash-lite: 5.311 seconds
- gemini-3.5-flash: 15.742 seconds
- Flash Lite's successful-request average was approximately 66.3% lower.
- Flash was approximately 2.96 times slower on this sample, based on successful-request averages.
Using all attempts, including failed calls:
- Flash Lite: 5.311 seconds
- Flash: 18.247 seconds
The two averages answer different questions. The successful-only average compares completed generations; the all-attempt average includes time spent on failed requests.
2.3 Repeated-run consistency
Consistency measure	gemini-3.5-flash-lite	gemini-3.5-flash
Scenarios tested	6/6	6/6
Scenarios with all 3 runs recorded	6/6	6/6
Scenarios valid in all 3 runs	6/6	3/6
Scenarios matching expected intent in all 3 runs	6/6	3/6
Scenarios with the same response-item count in all 3 runs	5/6	2/6
Scenarios with exactly identical full responses in all 3 runs	0/6	0/6


Exact-text equality is a strict measure for generative responses. Different wording does not, by itself, establish a semantic inconsistency. This benchmark did not include human or model-based semantic-equivalence grading.
3. Finding
gemini-3.5-flash-lite was the faster and more reliable model in this reduced sample.

It completed all 18 requests, returned valid responses matching the expected intent in all 18, and had a successful-request average latency of 5.311 seconds. gemini-3.5-flash had three timeouts and a successful-request average latency of 15.742 seconds.

This conclusion is limited to the six selected scenarios, three repetitions, the tested API environment, and the execution date. It should not be presented as a result for the entire 47-scenario dataset or as a universal model-performance claim.
4. Limitations
1. Reduced scenario coverage: 6 of the 47 official scenarios were tested. The result is a lead-approved sample, not a full-dataset evaluation.
2. Three repetitions: The team lead approved three repetitions for this comparison. The broader evaluation document separately describes a five-trial consistency requirement; this benchmark does not satisfy that broader requirement.
3. No semantic response grading: The script measured response validity, expected-intent match, response-item count consistency, and exact response equality. It did not judge whether differently worded responses were semantically equivalent, accurate, relevant, or useful.
4. Live-output count: There were 33 successful live model outputs (18 Flash Lite and 15 Flash). This is below the broader evaluation document's requirement to test at least 100 actual LLM outputs against the response schema.
5. Timeouts: The three Flash failures were reported by the terminal as APITimeoutError. The benchmark record stored a generic no-response message because the provider returned None; the raw terminal output is useful supporting evidence.
6. Environment-specific latency: Measured latency includes the API/network path and can vary with service load, quota, and network conditions.
5. Broader evaluation checklist — not completed by this benchmark
The Setu Guide AI/ML Intern 3 evaluation report lists additional work beyond this Gemini model comparison. This benchmark does not claim to complete those separate items:
- Broader live-response quality grading for accuracy, relevance, and usefulness.
- Five-trial consistency across the broader evaluation inputs.
- Dedicated safety red-team evaluation.
- Gemini-versus-OpenAI provider comparison, including a successful live OpenAI request.
- Verification of token-usage logging and pricing assumptions.
- At least 100 live LLM outputs checked against the relevant schema.
- Chat UI response-length and tone checks.
- Team-lead review of pipeline-to-orchestrator conversion and the final API response contract.
- Failure-owner review and final team-lead sign-off.
Whether those items are in scope for the current handoff should be confirmed with the team lead.
6. Reproducibility artifacts
Benchmark script: scripts/gemini_benchmark_sample.py
Raw results: eval/gemini_benchmark_sample_6scenarios_20261106.json
Official scenario source: teammate/data/scenarios-v1:data/scenarios_v1.json

The original 47-scenario benchmark script and its earlier pilot report were kept separate from this reduced-sample run.
Prepared for: Sambandh Setu team lead
Result classification: Reduced-sample, live Gemini comparison; not a full evaluation sign-off