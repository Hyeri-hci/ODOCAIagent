"""
실시간 성능 대시보드.

터미널에서 벤치마크 진행 상황을 실시간으로 모니터링합니다.
rich 라이브러리를 사용하여 프로그레스 바, 테이블, 라이브 업데이트를 지원합니다.

Usage:
    python backend/scripts/dashboard.py --repo Hyeri-hci/ODOCAIagent
    python backend/scripts/dashboard.py --scenario small_repo
    python backend/scripts/dashboard.py --watch
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.layout import Layout
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' library not installed. Install with: pip install rich")


@dataclass
class NodeStatus:
    """노드 실행 상태."""
    name: str
    status: str = "pending"  # pending, running, success, failed
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    message: str = ""


class PerformanceDashboard:
    """
    실시간 성능 대시보드.
    
    기능:
        - 프로그레스 바로 진행 상황 표시
        - 노드별 실행 상태 테이블
        - 실시간 메트릭 업데이트
        - 최종 결과 요약
    """
    
    META_FLOW_NODES = [
        "parse_supervisor_intent",
        "create_supervisor_plan",
        "execute_supervisor_plan",
        "reflect_supervisor",
        "finalize_supervisor_answer",
    ]
    
    DIAGNOSIS_NODES = [
        "fetch_readme",
        "fetch_activity",
        "analyze_dependencies",
        "calculate_scores",
        "generate_summary",
    ]
    
    def __init__(self, agent_type: str = "supervisor"):
        self.agent_type = agent_type
        self.console = Console() if RICH_AVAILABLE else None
        self.nodes: Dict[str, NodeStatus] = {}
        self.start_time: Optional[float] = None
        self.metrics: Dict[str, Any] = {}
        
        # 노드 초기화
        node_list = (
            self.META_FLOW_NODES if agent_type == "supervisor" 
            else self.DIAGNOSIS_NODES
        )
        for name in node_list:
            self.nodes[name] = NodeStatus(name=name)
    
    def start(self):
        """대시보드 시작."""
        self.start_time = time.time()
        if self.console:
            self.console.print(
                Panel(
                    f"[bold blue]{self.agent_type.upper()} Performance Dashboard[/bold blue]",
                    subtitle=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
    
    def update_node(
        self,
        name: str,
        status: str,
        message: str = "",
        duration_ms: float = 0.0
    ):
        """노드 상태 업데이트."""
        if name not in self.nodes:
            self.nodes[name] = NodeStatus(name=name)
        
        node = self.nodes[name]
        node.status = status
        node.message = message
        node.duration_ms = duration_ms
        
        if status == "running" and node.start_time is None:
            node.start_time = time.time()
        elif status in ("success", "failed"):
            node.end_time = time.time()
            if node.start_time and duration_ms == 0:
                node.duration_ms = (node.end_time - node.start_time) * 1000
    
    def set_metric(self, key: str, value: Any):
        """메트릭 설정."""
        self.metrics[key] = value
    
    def render_table(self) -> Table:
        """노드 상태 테이블 렌더링."""
        table = Table(title=f"{self.agent_type.upper()} Node Status")
        
        table.add_column("Node", style="cyan", width=30)
        table.add_column("Status", width=10)
        table.add_column("Duration", justify="right", width=12)
        table.add_column("Message", width=30)
        
        status_styles = {
            "pending": "[dim]pending[/dim]",
            "running": "[yellow]running[/yellow]",
            "success": "[green]success[/green]",
            "failed": "[red]failed[/red]",
        }
        
        for name, node in self.nodes.items():
            status_text = status_styles.get(node.status, node.status)
            duration_text = (
                f"{node.duration_ms:.2f}ms" if node.duration_ms > 0 else "-"
            )
            table.add_row(
                name,
                status_text,
                duration_text,
                node.message[:30] if node.message else ""
            )
        
        return table
    
    def render_metrics(self) -> Panel:
        """메트릭 패널 렌더링."""
        lines = []
        
        if self.start_time:
            elapsed = (time.time() - self.start_time) * 1000
            lines.append(f"Elapsed: {elapsed:.2f}ms")
        
        for key, value in self.metrics.items():
            if isinstance(value, float):
                lines.append(f"{key}: {value:.2f}")
            else:
                lines.append(f"{key}: {value}")
        
        content = "\n".join(lines) if lines else "No metrics yet"
        return Panel(content, title="Metrics")
    
    def show(self):
        """현재 상태 출력."""
        if not self.console:
            # rich 없이 기본 출력
            print("\n=== Dashboard Status ===")
            for name, node in self.nodes.items():
                print(f"  {name}: {node.status} ({node.duration_ms:.2f}ms)")
            return
        
        self.console.print(self.render_table())
        self.console.print(self.render_metrics())
    
    def run_with_live_update(self, benchmark_func):
        """
        실시간 업데이트와 함께 벤치마크 실행.
        
        Args:
            benchmark_func: 실행할 벤치마크 함수
        """
        if not RICH_AVAILABLE:
            # rich 없이 기본 실행
            return benchmark_func()
        
        with Live(self.render_table(), refresh_per_second=4, console=self.console) as live:
            # 백그라운드에서 벤치마크 실행
            result = [None]
            error = [None]
            
            def run():
                try:
                    result[0] = benchmark_func()
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=run)
            thread.start()
            
            # 실행 중 업데이트
            while thread.is_alive():
                live.update(self.render_table())
                time.sleep(0.25)
            
            thread.join()
            
            # 최종 상태 표시
            live.update(self.render_table())
            
            if error[0]:
                raise error[0]
            
            return result[0]
    
    def summary(self):
        """최종 요약 출력."""
        if not self.console:
            print("\n=== Summary ===")
            total_time = sum(n.duration_ms for n in self.nodes.values())
            print(f"Total Time: {total_time:.2f}ms")
            
            success = sum(1 for n in self.nodes.values() if n.status == "success")
            total = len(self.nodes)
            print(f"Success: {success}/{total}")
            return
        
        # rich 출력
        total_time = sum(n.duration_ms for n in self.nodes.values())
        success = sum(1 for n in self.nodes.values() if n.status == "success")
        failed = sum(1 for n in self.nodes.values() if n.status == "failed")
        
        summary_text = Text()
        summary_text.append(f"\nTotal Time: ", style="bold")
        summary_text.append(f"{total_time:.2f}ms\n", style="cyan")
        summary_text.append(f"Success: ", style="bold")
        summary_text.append(f"{success}", style="green")
        summary_text.append(f" / Failed: ", style="bold")
        summary_text.append(f"{failed}\n", style="red" if failed > 0 else "dim")
        
        self.console.print(Panel(summary_text, title="Summary"))


def run_dashboard_demo():
    """대시보드 데모 실행."""
    dashboard = PerformanceDashboard(agent_type="supervisor")
    dashboard.start()
    
    # 시뮬레이션
    for node in dashboard.META_FLOW_NODES:
        dashboard.update_node(node, "running")
        dashboard.show()
        time.sleep(0.5)
        
        duration = 100 + (hash(node) % 200)
        dashboard.update_node(node, "success", duration_ms=duration)
    
    dashboard.summary()


def main():
    parser = argparse.ArgumentParser(
        description="실시간 성능 대시보드",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Supervisor 벤치마크 실시간 모니터링
  python dashboard.py --repo Hyeri-hci/ODOCAIagent --type supervisor
  
  # Diagnosis 벤치마크 모니터링
  python dashboard.py --repo Hyeri-hci/ODOCAIagent --type diagnosis
  
  # 데모 모드
  python dashboard.py --demo
        """
    )
    
    parser.add_argument(
        "--repo",
        help="테스트할 레포지토리 (owner/repo 형식)"
    )
    parser.add_argument(
        "--type",
        choices=["supervisor", "diagnosis"],
        default="supervisor",
        help="에이전트 타입"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="데모 모드 실행"
    )
    
    args = parser.parse_args()
    
    if not RICH_AVAILABLE:
        print("Error: 'rich' library required. Install with: pip install rich")
        print("Running in basic mode...")
    
    if args.demo:
        run_dashboard_demo()
        return
    
    if not args.repo:
        print("Error: --repo required (or use --demo)")
        sys.exit(1)
    
    # 레포 파싱
    owner, repo = args.repo.split("/", 1)
    
    dashboard = PerformanceDashboard(agent_type=args.type)
    dashboard.start()
    
    if args.type == "supervisor":
        from backend.scripts.benchmark_supervisor import SupervisorBenchmark
        benchmark = SupervisorBenchmark(verbose=False)
        
        def run_benchmark():
            return benchmark.run_single(owner, repo)
        
        dashboard.run_with_live_update(run_benchmark)
    else:
        from backend.scripts.benchmark_diagnosis import DiagnosisBenchmark
        benchmark = DiagnosisBenchmark(verbose=False)
        
        def run_benchmark():
            return benchmark.run_single(owner, repo)
        
        dashboard.run_with_live_update(run_benchmark)
    
    dashboard.summary()


if __name__ == "__main__":
    main()
