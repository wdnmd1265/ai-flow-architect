"""
核心引擎组件

.. deprecated:: 2.0
    FlowArchitect, TaskScheduler, ContextManager, CacheManager 为 V1 遗留模块。
    活跃代码请使用 ``from audison.engine import TrustEngine``。
    这些模块将在 V3.0 正式移除。
"""

from .architect import FlowArchitect
from .scheduler import TaskScheduler
from .context import ContextManager
from .cache import CacheManager

__all__ = ["FlowArchitect", "TaskScheduler", "ContextManager", "CacheManager"]
