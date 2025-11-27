from backend.common.models import RepoMetrics

def compute_basic_metrics(metrics: RepoMetrics) -> float:
  """Computes a basic health score based on stars, forks, and open issues."""
  score = 0
  score += min(metrics.stars / 1000, 1.0) * 0.4
  score += min(metrics.forks / 500, 1.0) * 0.3
  score += min(metrics.watchers / 200, 1.0) * 0.3
  return score