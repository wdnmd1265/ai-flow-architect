"""
双脑系统

活跃模块：
- BrainTwo: 多仲裁者并行审查
- BrainOpponent: 反对者攻防
- BrainBlind: 无上下文盲审

.. deprecated::
    BrainOne（V1 蓝图生成脑）为 V1 遗留模块，将在 V3.0 正式移除。
"""

from .brain_one import BrainOne
from .brain_two import BrainTwo
from .brain_opponent import BrainOpponent
from .brain_blind import BrainBlind, BlindVerdict

__all__ = ["BrainOne", "BrainTwo", "BrainOpponent", "BrainBlind", "BlindVerdict"]
