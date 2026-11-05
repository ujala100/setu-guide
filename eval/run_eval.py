"""One-command lightweight evaluation for AI/ML Intern 1. Run: python eval/run_eval.py"""
import json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.router import route_intent
from app.safety.guard import check_input

def load(path): return json.loads(path.read_text(encoding='utf-8'))
def main():
 scenarios=load(ROOT/'data/conversations/scenarios_v2.json')['scenarios']
 red=load(ROOT/'data/conversations/red_team_v2.json')['cases']
 edges=load(ROOT/'data/conversations/edge_cases_v2.json')['cases']
 # Accuracy on the expected intent subset. Existing rule-based router may fail novel/ambiguous cases.
 correct=0; rows=[]
 for s in scenarios:
  got=route_intent(s['message'],s.get('quick_action'))
  ok=got==s['expected_intent']; correct+=ok
  rows.append({'id':s['scenario_id'],'expected':s['expected_intent'],'actual':got,'pass':ok})
 accuracy=correct/len(scenarios) if scenarios else 0
 # Relevance proxy: intent match is the measurable deterministic proxy; not a human quality judgment.
 relevance=accuracy
 safety_pass=0; safety_rows=[]
 for c in red:
  got={f.value for f in check_input(c['message'])}; ok=c['expected_flag'] in got; safety_pass+=ok
  safety_rows.append({'id':c['case_id'],'expected_flag':c['expected_flag'],'actual_flags':sorted(got),'pass':ok})
 # Consistency: deterministic router repeated 5 times per scenario; measure exact intent stability.
 consistency_pass=0
 for s in scenarios:
  runs=[route_intent(s['message'],s.get('quick_action')) for _ in range(5)]
  consistency_pass += len(set(runs))==1
 consistency=consistency_pass/len(scenarios) if scenarios else 0
 # Edge-case crash-free and expected flag checks; report only, not counted in main safety score.
 edge_rows=[]
 for c in edges:
  try:
   intent=route_intent(c['message'])
   flags={f.value for f in check_input(c['message'])}
   expected=set(c.get('expected_flags',[]))
   edge_rows.append({'id':c['case_id'],'category':c['category'],'no_crash':True,'expected_flags_found':expected.issubset(flags),'intent':intent,'flags':sorted(flags)})
  except Exception as e: edge_rows.append({'id':c['case_id'],'category':c['category'],'no_crash':False,'error':type(e).__name__})
 out={'version':'v2','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'counts':{'profiles':len(load(ROOT/'data/profiles/profiles_v2.json')['profiles']),'scenarios':len(scenarios),'edge_cases':len(edges),'red_team_cases':len(red)},'metrics':{'intent_accuracy':round(accuracy,4),'relevance_proxy_intent_match':round(relevance,4),'five_run_consistency':round(consistency,4),'red_team_pass_rate':round(safety_pass/len(red),4) if red else 0,'edge_cases_no_crash_rate':round(sum(x['no_crash'] for x in edge_rows)/len(edge_rows),4) if edge_rows else 0},'notes':['Relevance is approximated by intent match; human scoring is still needed.','Consistency currently tests deterministic router intent, not nondeterministic LLM reply consistency.','Baseline reflects this repository state and should be version-tagged at commit time.'],'scenario_results':rows,'red_team_results':safety_rows,'edge_case_results':edge_rows}
 (ROOT/'eval/results').mkdir(exist_ok=True)
 (ROOT/'eval/results/latest_v2.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
 print('SETU GUIDE AI/ML INTERN 1 EVALUATION — v2')
 print(f"Profiles: {out['counts']['profiles']} | Scenarios: {out['counts']['scenarios']} | Edge cases: {out['counts']['edge_cases']} | Red-team: {out['counts']['red_team_cases']}")
 for k,v in out['metrics'].items(): print(f'{k}: {v:.1%}')
 print(f"Detailed results: {ROOT/'eval/results/latest_v2.json'}")
if __name__=='__main__': main()
