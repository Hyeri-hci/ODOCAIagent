import unittest
import sys
import os
from dataclasses import dataclass, field
from typing import List

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.models import DependenciesSnapshot, DependencyInfo
from backend.core.scoring_core import compute_dependency_complexity

class TestDependencyComplexity(unittest.TestCase):
    def create_snapshot(self, deps: List[DependencyInfo]) -> DependenciesSnapshot:
        return DependenciesSnapshot(
            repo_id="test/repo",
            dependencies=deps,
            analyzed_files=["requirements.txt"],
            parse_errors=[]
        )

    def test_empty_dependencies(self):
        """의존성이 없는 경우 복잡도 0"""
        snapshot = self.create_snapshot([])
        score, flags = compute_dependency_complexity(snapshot)
        self.assertEqual(score, 0)
        self.assertEqual(flags, [])

    def test_low_complexity_repo(self):
        """의존성이 적고(30개 미만) 핀 고정 비율이 높은 경우"""
        deps = [
            DependencyInfo(name=f"lib-{i}", version="==1.0.0", source="req", dep_type="runtime")
            for i in range(10)
        ]
        snapshot = self.create_snapshot(deps)
        score, flags = compute_dependency_complexity(snapshot)
        
        # Base score for <30 deps is 20~40. 
        # 10 deps -> 20 + (10/30)*20 = 26.6 -> 26
        # Pinned ratio 1.0 -> No penalty
        self.assertLess(score, 40)
        self.assertEqual(flags, [])

    def test_many_dependencies_complexity(self):
        """의존성이 매우 많은(100개 이상) 경우"""
        deps = [
            DependencyInfo(name=f"lib-{i}", version="==1.0.0", source="req", dep_type="runtime")
            for i in range(110)
        ]
        snapshot = self.create_snapshot(deps)
        score, flags = compute_dependency_complexity(snapshot)
        
        # Base score for >100 deps is 70~90.
        # 110 deps -> 70 + min((10/100)*20, 20) = 72
        # Pinned ratio 1.0 -> No penalty
        self.assertGreater(score, 60)
        self.assertIn("many_dependencies", flags)

    def test_unpinned_dependencies_complexity(self):
        """핀 고정 비율이 낮은 경우"""
        # 10 deps, all unpinned (None or "*")
        deps = [
            DependencyInfo(name=f"lib-{i}", version=None, source="req", dep_type="runtime")
            for i in range(10)
        ]
        snapshot = self.create_snapshot(deps)
        score, flags = compute_dependency_complexity(snapshot)
        
        # Base score for 10 deps -> ~26
        # Pinned ratio 0.0 -> <0.3 -> +15 penalty
        # Total ~41
        self.assertGreater(score, 30)
        self.assertIn("unpinned_dependencies", flags)

if __name__ == "__main__":
    unittest.main()
