import asyncio
import time

async def run_all_tests():
    print()
    print('=' * 70)
    print('  ODOC Backend Agent Integration Tests')
    print('=' * 70)
    print()
    
    # ===== TEST 1: Diagnosis =====
    print('[1/4] Diagnosis Agent - pallets/click')
    print('-' * 50)
    
    from backend.agents.diagnosis.graph import run_diagnosis
    
    start = time.time()
    diag_result = await run_diagnosis(
        owner='pallets',
        repo='click',
        user_message='analyze'
    )
    t1 = time.time() - start
    
    print('  Time:', round(t1, 2), 'sec')
    print('  Health:', diag_result.get('health_score'), '/ Onboarding:', diag_result.get('onboarding_score'))
    print()
    
    # ===== TEST 2: Comparison (1st run) =====
    print('[2/4] Comparison Agent - flask vs click (1st run)')
    print('-' * 50)
    
    from backend.agents.comparison.graph import run_comparison_graph
    
    start = time.time()
    comp_result = await run_comparison_graph(
        repos=['pallets/flask', 'pallets/click'],
        use_cache=True
    )
    t2 = time.time() - start
    
    print('  Time:', round(t2, 2), 'sec')
    print('  Cache hits:', comp_result.get('cache_hits', []))
    print('  Cache misses:', comp_result.get('cache_misses', []))
    
    recs = comp_result.get('agent_analysis', {}).get('recommendations', {})
    winner = recs.get('overall_winner', {})
    if winner:
        print('  Winner:', winner.get('repo', 'N/A'))
    print()
    
    # ===== TEST 3: Comparison (2nd run - cache) =====
    print('[3/4] Comparison Agent - flask vs click (2nd run - cache test)')
    print('-' * 50)
    
    start = time.time()
    comp_result2 = await run_comparison_graph(
        repos=['pallets/flask', 'pallets/click'],
        use_cache=True
    )
    t3 = time.time() - start
    
    print('  Time:', round(t3, 2), 'sec')
    print('  Cache hits:', comp_result2.get('cache_hits', []))
    print('  Cache misses:', comp_result2.get('cache_misses', []))
    
    if t3 < t2 / 2:
        print('  [OK] Cache working! ' + str(round(t2/t3, 1)) + 'x faster')
    print()
    
    # ===== TEST 4: Onboarding =====
    print('[4/4] Onboarding Agent - pallets/click (beginner)')
    print('-' * 50)
    
    from backend.agents.onboarding.graph import run_onboarding_graph
    
    start = time.time()
    onb_result = await run_onboarding_graph(
        owner='pallets',
        repo='click',
        experience_level='beginner'
    )
    t4 = time.time() - start
    
    print('  Time:', round(t4, 2), 'sec')
    print('  Plan weeks:', len(onb_result.get('plan', [])))
    print('  Issues found:', len(onb_result.get('candidate_issues', [])))
    
    error = onb_result.get('error')
    if error:
        print('  ERROR:', error)
    print()
    
    # ===== Summary =====
    print('=' * 70)
    print('  TEST SUMMARY')
    print('=' * 70)
    print('  [1] Diagnosis:      ', round(t1, 2), 'sec - Health', diag_result.get('health_score'))
    print('  [2] Comparison 1st: ', round(t2, 2), 'sec')
    print('  [3] Comparison 2nd: ', round(t3, 2), 'sec (cached)')
    print('  [4] Onboarding:     ', round(t4, 2), 'sec -', len(onb_result.get('plan', [])), 'weeks plan')
    print()
    print('  Total time:', round(t1+t2+t3+t4, 2), 'sec')
    print('=' * 70)

asyncio.run(run_all_tests())