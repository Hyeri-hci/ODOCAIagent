import re
from typing import List, Dict
from datetime import timedelta, timezone
from core.github.schema import ParsedRepo # ParsedRepo는 mutable 객체라고 가정
from core.github.fetcher import GitHubDetailFetcher
from utils.date import DateUtilsUTC

class RepoFilter:
    """
    [Strict Rule Based Filter - High Standard]
    활발한 오픈소스 프로젝트 기준을 적용하여 필터링합니다.
    """

    # 월간 기준 활성도 (High Standard)
    BASE_RATE_MANY = {
        "commits": 30, 
        "issues": 10,  
        "prs": 10 
    }

    # 적음(Few)의 기준 (절대값)
    THRESHOLD_FEW_ABSOLUTE = 5 
    
    # API 효율성을 위한 최대 검사 상한선
    MAX_CHECK_CAP = 100

    def __init__(self):
        self.fetcher = GitHubDetailFetcher()

    def filter_repositories(self, repos: List[ParsedRepo], criteria: Dict) -> List[ParsedRepo]:
        other_condition = criteria.get("other")
        
        if not other_condition:
            print("✅ [RepoFilter] No specific 'other' conditions found. Returning all repos.")
            # 💡 [Note] 필터가 없더라도 모든 repo에 activity_stats를 빈 딕셔너리로 초기화해야 할 수 있습니다. 
            # (현재 로직에서는 필터가 없으면 초기화되지 않음)
            return repos
        
        if isinstance(other_condition, list):
            other_condition = " ".join(other_condition)
            
        self.now = DateUtilsUTC.now()
        filtered_repos = []
        conditions = other_condition.split()

        print(f"🔍 [RepoFilter] Applying High-Standard filters: {conditions}")

        for repo in repos:
            print(f"\n--- ⏳ Checking Repo: {repo.owner}/{repo.name} ---")
            
            # 모든 repo에 activity_stats를 초기화하고 필터링을 진행합니다.
            if self._check_all_conditions(repo, conditions):
                print(f"✅ PASS: Repository {repo.owner}/{repo.name} passed ALL conditions.")
                filtered_repos.append(repo)
            else:
                print(f"❌ FAIL: Repository {repo.owner}/{repo.name} failed at least one condition.")

        print(f"\n✅ [RepoFilter] Filtering complete. Kept {len(filtered_repos)} out of {len(repos)}.")
        return filtered_repos

    def _check_all_conditions(self, repo: ParsedRepo, conditions: List[str]) -> bool:
        # 🌟 [핵심 수정] 활동성 지표 저장용 딕셔너리를 repo 객체에 추가
        repo.activity_stats = {} 
        
        all_passed = True
        for condition in conditions:
            # Note: _dispatch_condition 내에서 fetcher API 호출 및 valid_count 계산이 이루어집니다.
            if not self._dispatch_condition(repo, condition):
                print(f"   [Condition Fail] Repo failed on condition: '{condition}'")
                all_passed = False
                
        # 모든 조건을 검사해야 모든 activity_stats가 채워지므로, 루프가 끝난 후 최종 결과를 반환합니다.
        return all_passed

    def _dispatch_condition(self, repo: ParsedRepo, condition: str) -> bool:
        # 1. 파싱 (Target, Action, Duration, Explicit_Num 추출)
        target = "commits" # 기본값
        if "issues" in condition: target = "issues"
        elif "prs" in condition: target = "prs"

        action = "has" # 기본값
        if "many" in condition: action = "many"
        elif "few" in condition: action = "few"
        elif "has" in condition: action = "has"
        
        months = 6 # 기본 6개월
        match_y = re.search(r"_(\d+)y", condition)
        match_m = re.search(r"_(\d+)m", condition)
        if match_y: months = int(match_y.group(1)) * 12
        elif match_m: months = int(match_m.group(1))
        
        explicit_num = None
        match_num = re.search(r"_(\d+)$", condition)
        if match_num and not condition.endswith("y") and not condition.endswith("m"):
            explicit_num = int(match_num.group(1))

        # 2. 목표 수량(Target Count) 계산
        target_count = 1
        
        if explicit_num:
            target_count = explicit_num
        elif action == "many":
            base_rate = self.BASE_RATE_MANY.get(target, 10)
            calculated_target = base_rate * months
            target_count = min(calculated_target, self.MAX_CHECK_CAP)
            target_count = max(target_count, 10)
            
        elif action == "few":
            target_count = self.THRESHOLD_FEW_ABSOLUTE
            
        print(f"   [Condition Parse] '{condition}' -> Target: {target}, Action: {action}, Months: {months}, Goal: {target_count}")

        # 3. 실행
        return self._check_items(repo, target, action, months, target_count)

    def _check_items(self, repo: ParsedRepo, target_type: str, action: str, months: int, target_count: int) -> bool:
        
        limit_date = self.now - timedelta(days=months*30)
        
        # Commits + Has (최근 푸시 날짜만 확인하는 최적화)
        if target_type == "commits" and action == "has":
             if not repo.last_push:
                 print(f"      [{target_type}] FAIL: No last_push data.")
                 return False
             last_push = repo.last_push.replace(tzinfo=timezone.utc) if repo.last_push.tzinfo is None else repo.last_push
             result = last_push >= limit_date
             print(f"      [{target_type}] Check last push ({last_push.strftime('%Y-%m-%d')}) vs Limit ({limit_date.strftime('%Y-%m-%d')}): {'PASS' if result else 'FAIL'}")
             
             # 🌟 [통합] 최적화된 경우, 유효성만 저장 (count는 0 또는 1로 간주)
             repo.activity_stats[f'check_period_months'] = months
             repo.activity_stats[f'check_type_{target_type}'] = action
             
             return result

        # Fetch Limit 설정
        fetch_limit = min(target_count + 5, self.MAX_CHECK_CAP) 
        
        # 💡 API 호출 (실제로는 이 부분에서 네트워크 I/O 발생)
        items = []
        if target_type == "issues":
            items = self.fetcher.fetch_recent_issues(repo.owner, repo.name, limit=fetch_limit)
        elif target_type == "prs":
            items = self.fetcher.fetch_recent_prs(repo.owner, repo.name, limit=fetch_limit)
        elif target_type == "commits":
            items = self.fetcher.fetch_recent_commits(repo.owner, repo.name, limit=fetch_limit)

        print(f"      [API Call] Fetched {len(items)} {target_type} (Limit: {fetch_limit}, Period Limit: {limit_date.strftime('%Y-%m-%d')}).")

        # 기간 필터링
        valid_count = 0
        for item in items:
            item_date = None
            if hasattr(item, 'created_at'): item_date = item.created_at
            elif hasattr(item, 'date'): item_date = item.date
            
            if item_date:
                item_date = item_date.replace(tzinfo=timezone.utc) if item_date.tzinfo is None else item_date
                if item_date >= limit_date:
                    valid_count += 1
        
        # 🌟 [핵심 수정] 계산된 유효 개수를 repo 객체에 통합
        repo.activity_stats[f'recent_{target_type}'] = valid_count 
        repo.activity_stats[f'check_period_months'] = months 
        repo.activity_stats[f'check_type_{target_type}'] = action
        
        # 최종 비교
        if action == "few":
            result = valid_count <= target_count
            print(f"      [{target_type}] Check FEW ({valid_count} <= {target_count}): {'PASS' if result else 'FAIL'}")
            return result
        else:
            result = valid_count >= target_count
            print(f"      [{target_type}] Check MANY/HAS ({valid_count} >= {target_count}): {'PASS' if result else 'FAIL'}")
            return result