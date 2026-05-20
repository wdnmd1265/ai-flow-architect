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
        choice_distribution = {}
        recent_rejections = []
        
        for d in decisions:
            profile = d.get("task_profile", {})
            domain = profile.get("domain", "unknown")
            complexity = profile.get("complexity", "unknown")
            
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
            
            choice = d.get("user_choice", "unknown")
            choice_distribution[choice] = choice_distribution.get(choice, 0) + 1
            
            if d.get("regret"):
                recent_rejections.append({
                    "task_id": d.get("task_id"),
                    "domain": domain,
                    "choice": choice,
                    "reason": d.get("reason", ""),
                })
        
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
            "choice_distribution": choice_distribution,
            "recent_regrets": recent_rejections[-5:],  # 最近5次后悔
        }

    async def mark_regret(self, task_id: str, reason: str = ""):
        """
        标记一次后悔（用户后悔选了某个方案）
        
        Args:
            task_id: 任务ID
            reason: 后悔原因
        """
        if not self.decisions_file.exists():
            logger.warning(f"决策文件不存在，无法标记后悔: {task_id}")
            return
        
        # 读取所有记录，找到对应 task_id 并标记
        decisions = []
        found = False
        try:
            with open(self.decisions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        if d.get("task_id") == task_id:
                            d["regret"] = True
                            d["regret_reason"] = reason
                            d["regret_timestamp"] = datetime.now().isoformat()
                            found = True
                        decisions.append(d)
        except Exception as e:
            logger.error(f"读取决策文件失败: {e}")
            return
        
        if not found:
            logger.warning(f"未找到 task_id {task_id}，无法标记后悔")
            return
        
        # 重写文件
        try:
            with open(self.decisions_file, "w", encoding="utf-8") as f:
                for d in decisions:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
            logger.info(f"后悔标记成功: {task_id}")
        except Exception as e:
            logger.error(f"写入决策文件失败: {e}")

    async def get_shadow_suggestion(self, task_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取影子建议 —— 在审批时调用，展示历史决策模式
        
        Args:
            task_profile: 当前任务的属性标签
            
        Returns:
            影子建议字典
        """
        all_decisions = await self.get_decisions(limit=1000)
        total = len(all_decisions)
        required = 10
        
        # 冷启动
        if total == 0:
            return {
                "status": "cold_start",
                "suggestion": "这是你的第一次决策。影子系统将开始记录。",
                "progress": f"完成 {required - total} 次决策后激活影子建议。",
                "remaining": required - total,
                "total_required": required,
            }
        
        if total < required:
            return {
                "status": "accumulating",
                "suggestion": f"影子正在学习你的决策风格...",
                "progress": f"已完成 {total}/{required} 次决策，再做 {required - total} 次后激活建议。",
                "remaining": required - total,
                "total_required": required,
                "total_decisions": total,
            }
        
        # 精确匹配：domain + complexity 都相同
        domain = task_profile.get("domain", "unknown")
        complexity = task_profile.get("complexity", "unknown")
        
        exact_matches = []
        loose_matches = []
        regrets = []
        
        for d in all_decisions:
            p = d.get("task_profile", {})
            if p.get("domain") == domain:
                loose_matches.append(d)
                if p.get("complexity") == complexity:
                    exact_matches.append(d)
            if d.get("regret"):
                regrets.append(d)
        
        # 构建建议
        exact_count = len(exact_matches)
        loose_count = len(loose_matches)
        
        if exact_count == 0 and loose_count == 0:
            return {
                "status": "no_match",
                "suggestion": "影子系统暂未找到类似决策记录。",
                "exact_matches": 0,
                "loose_matches": 0,
                "total_decisions": total,
            }
        
        # 分析匹配记录的决策倾向
        source = exact_matches if exact_count > 0 else loose_matches
        source_label = "精确匹配" if exact_count > 0 else "宽松匹配" if loose_count > 0 else "近似"
        
        # 构建决策倾向
        return {
            "status": "ok",
            "suggestion": f"基于 {len(source)} 条{source_label}历史，你的决策倾向如下。",
            "exact_matches": exact_count,
            "loose_matches": loose_count,
            "total_decisions": total,
            "recent_regrets": [
                {
                    "task_id": r.get("task_id", ""),
                    "domain": r.get("task_profile", {}).get("domain", ""),
                    "choice": r.get("user_choice", ""),
                    "reason": r.get("regret_reason", r.get("reason", "")),
                }
                for r in regrets[-3:]
            ],
            "regret_count": len(regrets),
            "source": source_label,
        }
