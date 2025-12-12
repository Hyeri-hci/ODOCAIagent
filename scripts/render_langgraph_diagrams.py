"""Utility script to export LangGraph diagrams for Diagnosis / Comparison agents.

Usage (from repo root):

    python -m scripts.render_langgraph_diagrams

This will generate Mermaid (.mmd) and, if supported by the installed langgraph
version, PNG files under docs/architecture/graphs/.
"""
from __future__ import annotations

import os
import logging
from typing import Any

from backend.agents.diagnosis.graph import get_diagnosis_graph
from backend.agents.comparison.graph import get_comparison_graph

logger = logging.getLogger(__name__)


def _ensure_output_dir() -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))  # repo root
    out_dir = os.path.join(base_dir, "docs", "architecture", "graphs")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _get_inner_graph(graph: Any) -> Any:
    """Best-effort helper to get the underlying graph object.

    Depending on langgraph versions, get_diagnosis_graph() may already return a
    compiled graph with a get_graph() method, or the raw graph itself.
    """

    if hasattr(graph, "get_graph") and callable(getattr(graph, "get_graph")):
        try:
            return graph.get_graph()  # type: ignore[no-any-return]
        except TypeError:
            # Some versions may require arguments; fall back to raw graph
            logger.warning("get_graph() call failed; using raw graph object instead")
            return graph
    return graph


def _export_mermaid(inner_graph: Any, out_path: str) -> None:
    """Export Mermaid source if the graph supports it."""

    mermaid = None

    if hasattr(inner_graph, "draw_mermaid"):
        draw_mermaid = getattr(inner_graph, "draw_mermaid")
        try:
            mermaid = draw_mermaid()  # type: ignore[assignment]
        except TypeError:
            # Some implementations may accept options; try without capturing return
            logger.warning("draw_mermaid() signature unexpected; attempting call without capture")
            draw_mermaid()
    elif hasattr(inner_graph, "to_mermaid"):
        mermaid = inner_graph.to_mermaid()  # type: ignore[assignment]

    if isinstance(mermaid, str):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(mermaid)
        logger.info("Mermaid diagram written: %s", out_path)
    else:
        logger.warning("Mermaid export not supported on this langgraph version for %s", out_path)


def _export_png(inner_graph: Any, out_path: str) -> None:
    """Export PNG diagram if the graph supports it.

    Note: This usually requires graphviz or a similar backend installed.
    """

    if hasattr(inner_graph, "draw_png"):
        draw_png = getattr(inner_graph, "draw_png")
        try:
            draw_png(out_path)
        except TypeError:
            # Some implementations may use a named argument
            try:
                draw_png(path=out_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("draw_png() failed: %s", exc)
                return
        except Exception as exc:  # pragma: no cover - defensive
            # e.g. ImportError: pygraphviz not installed
            logger.warning("PNG export skipped: %s", exc)
            return
        logger.info("PNG diagram written: %s", out_path)
    else:
        logger.warning("PNG export not supported on this langgraph version for %s", out_path)


def export_diagnosis_graph() -> None:
    graph = get_diagnosis_graph()
    inner = _get_inner_graph(graph)

    out_dir = _ensure_output_dir()
    mermaid_path = os.path.join(out_dir, "diagnosis_graph.mmd")
    png_path = os.path.join(out_dir, "diagnosis_graph.png")

    _export_mermaid(inner, mermaid_path)
    _export_png(inner, png_path)


def export_comparison_graph() -> None:
    graph = get_comparison_graph()
    inner = _get_inner_graph(graph)

    out_dir = _ensure_output_dir()
    mermaid_path = os.path.join(out_dir, "comparison_graph.mmd")
    png_path = os.path.join(out_dir, "comparison_graph.png")

    _export_mermaid(inner, mermaid_path)
    _export_png(inner, png_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logger.info("Exporting LangGraph diagrams (Diagnosis / Comparison)")

    export_diagnosis_graph()
    export_comparison_graph()

    logger.info("Done. Check docs/architecture/graphs/ for output files.")


if __name__ == "__main__":  # pragma: no cover
    main()
