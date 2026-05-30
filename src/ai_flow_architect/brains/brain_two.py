"""
二号脑 - 质量仲裁官
"""

import asyncio
import json
import os
from typing import Dict, Any, List
from loguru import logger

from ..utils.llm_client import LLMClient


class BrainTwo:
    """
    二号脑 - 质量仲裁官

    独立的质量审核系统，与一号脑使用不同的模型实例。
    负责多仲裁者并行审查 AI 产出。

    单 key 模式下：框架会自动为 brain2 选择同提供商的更便宜模型，
    基本可用的质检效果。如需最佳效果，请配置双 key 跨提供商使用。
    """
    
    def __init__(self, model: str = "gpt-4"):
        """
        初始化二号脑
        
        Args:
            model: 使用的模型
        """
        self.model = model
        self.llm_client = LLMClient(model)
        logger.info(f"二号脑初始化完成，使用模型: {model}")

    def _configure_arbiters(self) -> List[Dict[str, Any]]:
        """配置3个仲裁者。多API→不同模型；单API→同模型不同温度+角色。"""
        available = [n for n, e in {
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
            "DashScope": "DASHSCOPE_API_KEY",
            "DeepSeek": "DEEPSEEK_API_KEY",
        }.items() if os.getenv(e)]

        if len(available) >= 3:
            return [
                {"model": "gpt-4o", "temperature": 0.2, "role": "严格审查员"},
                {"model": "claude-3-5-sonnet-20241022", "temperature": 0.3, "role": "架构师审查"},
                {"model": "deepseek-chat", "temperature": 0.3, "role": "代码审查员"},
            ]
        else:
            return [
                {"model": self.model, "temperature": 0.2, "role": "严格审查员"},
                {"model": self.model, "temperature": 0.4, "role": "架构师视角审查"},
                {"model": self.model, "temperature": 0.6, "role": "用户体验审查"},
            ]

    async def audit_raw(
        self,
        requirement: str,
        ai_output: str,
    ) -> Dict[str, Any]:
        """
        审查任意 AI 产出，不依赖 Blueprint 对象。
        
        供 TrustEngine、API 壳、GitHub Action 等外部调用。
        
        Args:
            requirement: 用户需求描述
            ai_output: AI 生成的产出（代码、文章、方案等）
            
        Returns:
            审查结果字典，包含 arbiter_votes 供 TrustReport 使用
        """
        arbiters = self._configure_arbiters()
        logger.info(f"audit_raw 启动 | {len(arbiters)} 个仲裁者 | 需求长度: {len(requirement)} | 产出长度: {len(ai_output)}")
        
        tasks = [
            self._single_arbiter_audit_raw(arb, requirement, ai_output)
            for arb in arbiters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        arbiter_votes = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"仲裁者 {i+1} 失败: {r}")
            else:
                valid_results.append(r)
                arbiter_votes.append({
                    "model": r.get("model", "unknown"),
                    "role": r.get("arbiter", "unknown"),
                    "passed": r.get("passed", False),
                    "score": r.get("score", 0),
                    "issues": r.get("issues", []),
                    "suggestions": r.get("suggestions", []),
                })
        
        if not valid_results:
            logger.error("所有仲裁者均失败")
            return {
                "passed": False,
                "score": 0,
                "issues": [{"type": "audit_error", "description": "所有仲裁者均失败", "severity": "high"}],
                "suggestions": [],
                "arbiter_votes": [],
            }
        
        # 合并结果
        scores = [r.get("score", 0) for r in valid_results]
        avg_score = sum(scores) / len(scores) if scores else 0
        all_issues = []
        all_suggestions = []
        
        for r in valid_results:
            all_suggestions.extend(r.get("suggestions", []))
            for issue in r.get("issues", []):
                all_issues.append(issue)
        
        from collections import Counter
        desc_counts = Counter(i.get("description", "") for i in all_issues)
        consensus_issues = [
            {"description": d, "count": c, "severity": "high"}
            for d, c in desc_counts.items() if c >= 2
        ]
        
        result = {
            "passed": sum(1 for r in valid_results if r.get("passed")) >= len(valid_results) * 0.5,
            "score": round(avg_score, 1),
            "issues": all_issues,
            "consensus_issues": consensus_issues,
            "suggestions": list(dict.fromkeys(all_suggestions)),
            "arbiter_votes": arbiter_votes,
            "isolation_level": "full" if len(set(r.get("model", "") for r in valid_results)) >= 2 else "degraded",
        }
        
        logger.info(f"audit_raw 完成 | 均分: {avg_score:.1f} | 问题: {len(all_issues)} | 一致缺陷: {len(consensus_issues)}")
        return result

    async def _single_arbiter_audit_raw(
        self, arbiter: Dict[str, Any], requirement: str, ai_output: str
    ) -> Dict[str, Any]:
        """
        单个仲裁者审查原始输入（不依赖 Blueprint）。
        
        Args:
            arbiter: 仲裁者配置
            requirement: 用户需求
            ai_output: AI 产出
            
        Returns:
            审查结果
        """
        temp_model = arbiter.get("model", self.model)
        temp_temp = arbiter.get("temperature", 0.3)
        temp_role = arbiter.get("role", "审核员")
        
        client = LLMClient(model=temp_model) if temp_model != self.model else self.llm_client
        
        system_prompt = f"""你是一名{temp_role}，审查 AI 生成的产出是否满足用户需求。

审查维度：
1. 需求匹配度：产出是否完整实现了需求中描述的功能
2. 安全性：是否存在安全漏洞（SQL注入、XSS、硬编码密钥等）
3. 逻辑正确性：代码逻辑是否正确，边界条件是否处理
4. 副作用：是否引入了需求中没提到的副作用

输出JSON:
{{
  "passed": true/false,
  "score": 85.0,
  "issues": [{{"type": "...", "step_name": "...", "severity": "high/medium/low", "description": "..."}}],
  "suggestions": ["..."]
}}"""
        
        # 截断过长的产出
        truncated_output = ai_output[:3000] + "..." if len(ai_output) > 3000 else ai_output
        audit_input = f"需求：{requirement}\n\nAI 产出：\n{truncated_output}"
        
        try:
            response = await client.audit(
                system_prompt=system_prompt, audit_input=audit_input, temperature=temp_temp
            )
            result = json.loads(response)
            return {
                "arbiter": temp_role, "model": temp_model, "temperature": temp_temp,
                "passed": result.get("passed", False), "score": result.get("score", 0),
                "issues": result.get("issues", []), "suggestions": result.get("suggestions", []),
            }
        except json.JSONDecodeError:
            logger.warning(f"仲裁者 {temp_role} 返回非JSON响应，使用降级结果")
            return {"arbiter": temp_role, "model": temp_model, "passed": False, "score": 0,
                    "issues": [{"type": "invalid_json", "description": "LLM returned non-JSON output", "severity": "high"}],
                    "suggestions": []}
        except Exception as e:
            logger.warning(f"仲裁者 {temp_role} 失败: {e}")
            return {"arbiter": temp_role, "model": temp_model, "passed": False, "score": 0, "issues": [], "suggestions": []}
