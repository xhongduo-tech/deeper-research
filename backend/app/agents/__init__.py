"""
Agent helpers retained for the unified pipeline and standalone APIs.

The legacy multi-agent classes (Planner/Research/Verifier/Reviewer/etc.) were
retired with the swarm engine. These remain because live code depends on them:
DataAnalystAgent (Excel grounding skills), plus OntologyAgent / SentimentAgent
which are imported directly from their modules by the ontology / sentiment APIs.
"""

from .data_analyst import DataAnalystAgent

__all__ = [
    "DataAnalystAgent",
]
