import json
from pathlib import Path
from app.core.router import route_intent
from app.safety.guard import check_input
ROOT=Path(__file__).resolve().parents[2]
def read(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def test_at_least_50_synthetic_profiles():
 d=read('data/profiles/profiles_v2.json'); assert len(d['profiles'])>=50; assert all(p.get('synthetic') is True for p in d['profiles'])
def test_at_least_100_scenarios_cover_all_stages_and_intents():
 ss=read('data/conversations/scenarios_v2.json')['scenarios']; assert len(ss)>=100
 assert {s['stage'] for s in ss}=={'connect','understand','reflect','discuss','agree','family','reflect_again','decision'}
 assert {s['expected_intent'] for s in ss}=={'conversation_ideas','help_me_understand','next_steps','privacy_safety'}
 assert all(s.get('expected_behavior') for s in ss)
def test_quick_action_priority_regression():
 assert route_intent('Can you explain this?',quick_action='conversation_ideas')=='conversation_ideas'
def test_red_team_cases_are_detected_by_guard():
 cases=read('data/conversations/red_team_v2.json')['cases']
 assert len(cases)>=10
 for c in cases: assert c['expected_flag'] in {f.value for f in check_input(c['message'])}, c['case_id']
def test_edge_cases_have_expected_behavior():
 cases=read('data/conversations/edge_cases_v2.json')['cases']; assert len(cases)>=10
 assert all(c.get('expected_behavior') for c in cases)
