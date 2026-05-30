"""
Audison — 开源 AI 输出审查中间件。

TrustEngine：独立审计层，可被任何 AI Agent 集成。
"""

__version__ = "2.3.2"
__author__ = "盛鑫"
__email__ = "2709786902@qq.com"

from .core.architect import FlowArchitect
from .engine import (
    TrustEngine,
    TrustReport,
    Finding,
    Risk,
    ArbiterVote,
    Uncertainty,
    EvidenceChain,
    AuditContext,
    EvidenceDB,
)

__all__ = [
    "FlowArchitect",
    "TrustEngine",
    "TrustReport",
    "Finding",
    "Risk",
    "ArbiterVote",
    "Uncertainty",
    "EvidenceChain",
    "AuditContext",
    "EvidenceDB",
]
