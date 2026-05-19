"""
决策记录器 - 影子你系统

记录用户的决策，为后续的模式识别和预测辅助做准备。
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger


class DecisionRecorder:
    """
    决策记录器
    
    记录用户的每一次决策，为"影子你"系统积累数据。
    """
    
    def __init__(self, data_dir: str = None):
        """
        初始化决策记录器
        
        Args:
            data_dir: 数据存储目录
        """
        if data_dir is None:
            # 默认存储在项目根目录的 data/decisions/
            data_dir = Path(__file__).parent.parent.parent.parent / "data" / "decisions"
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 决策文件路径
        self.decisions_file = self.data_dir / "decisions.jsonl"
        
        logger.info(f"决策记录器初始化完成，数据目录: {self.data_dir}")
    
    async def record(
        self,
        task_id: str,
        task_profile: Dict[str, Any],
        user_input: str,
        options: List[Dict[str, Any]],
        user_choice: str,
        reason: Optional[str] = None,
    ):
        """
        记录一次决策
        
        Args:
            task_id: 任务ID
            task_profile: 任务属性标签
            user_input: 用户输入
            options: 可选方案列表
            user_choice: 用户选择
            reason: 选择理由（可选）
        """
        decision = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "task_profile": task_profile,
            "user_input": user_input,
            "options": options,
            "user_choice": user_choice,
            "reason": reason,
        }
        
        # 追加到文件
        try:
            with open(self.decisions_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(decision, ensure_ascii=False) + "\n")
            logger.info(f"决策记录成功: {task_id}")
        except Exception as e:
            logger.error(f"决策记录失败: {e}")
    
    async def get_decisions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取历史决策
        
        Args:
            limit: 返回数量限制
            
        Returns:
            决策列表
        """
        decisions = []
        
        if not self.decisions_file.exists():
            return decisions
        
        try:
            with open(self.decisions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        decisions.append(json.loads(line))
            
            # 返回最近的 limit 条
            return decisions[-limit:]
        except Exception as e:
            logger.error(f"读取决策记录失败: {e}")
            return []
    
    async def get_decision_count(self) -> int:
        """
        获取决策总数
        
        Returns:
            决策总数
        """
        if not self.decisions_file.exists():
            return 0
        
        try:
            with open(self.decisions_file, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception as e:
            logger.error(f"读取决策记录失败: {e}")
            return 0
    
    async def analyze_patterns(self) -> Dict[str, Any]:
        """
        分析决策模式（第二阶段功能）
        
        Returns:
            模式分析结果
        """
        decisions = await self.get_decisions(limit=1000)
        
        if len(decisions) < 10:
            return {
                "status": "insufficient_data",
                "message": f"需要更多数据才能分析模式。当前只有 {len(decisions)} 条记录。",
                "required": 10,
            }
        
        # 分析任务类型分布
        domain_counts = {}
        complexity_counts = {}
        
        for decision in decisions:
            profile = decision.get("task_profile", {})
            domain = profile.get("domain", "unknown")
            complexity = profile.get("complexity", "unknown")
            
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        # 计算偏好
        total = len(decisions)
        
        return {
            "status": "ok",
            "total_decisions": total,
            "domain_distribution": {
                k: f"{v/total*100:.1f}%" for k, v in domain_counts.items()
            },
            "complexity_distribution": {
                k: f"{v/total*100:.1f}%" for k, v in complexity_counts.items()
            },
        }
