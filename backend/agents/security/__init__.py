"""
Security analysis module for analyzing dependencies in GitHub repositories
"""
from .service import SecurityAnalysisService, analyze_repository
from .github import GitHubClient, RepositoryAnalyzer
from .models import Dependency, DependencyFile
from .extractors import DependencyExtractor

__version__ = "1.0.0"

__all__ = [
    "SecurityAnalysisService",
    "analyze_repository",
    "GitHubClient",
    "RepositoryAnalyzer",
    "Dependency",
    "DependencyFile",
    "DependencyExtractor",
]
