from backend.common.models import RepoMetrics
from .chaoss_metrics import compute_basic_metrics

def calculate_health_score(metrics: RepoMetrics) -> float:
    """Calculates the health score of a repository based on its metrics."""
    health_score = compute_basic_metrics(metrics) * 100  # Scale to 0-100
    return round(health_score, 1)