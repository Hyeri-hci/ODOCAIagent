"""
GitHub integration module
"""
from .client import GitHubClient
from .analyzer import RepositoryAnalyzer

__all__ = ['GitHubClient', 'RepositoryAnalyzer']
