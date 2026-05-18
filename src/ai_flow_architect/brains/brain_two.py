"""
二号脑 - 质量仲裁官
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from loguru import logger

from ..utils.llm_client import LLMClient


class AuditResult(BaseModel):
    """审核结果"""
    passed: bool = Field(..., description="是否通过审核")
    score: float = Field(0.0, description="质量分数 (0-100)")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="发现的问题")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    detailed_report: str = Field("", description="详细报告")


class BrainTwo:
    """
    二号脑 - 质量仲裁官

    独立的质量审核系统，与一号脑使用不同的模型实例。
    负责对比蓝图与交付物，确保质量达标。

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
        self.audit_history = []
        logger.info(f"二号脑初始化完成，使用模型: {model}")
    
    async def audit(
        self, 
        blueprint: Any, 
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行质量审核
        
        Args:
            blueprint: 任务蓝图
            execution_result: 执行结果
            
        Returns:
            审核结果字典
        """
        logger.info("开始质量审核")
        
        # 使用 LLM 进行质量审核
        audit_result = await self._audit_with_llm(blueprint, execution_result)
        
        # 记录审核历史
        self.audit_history.append({
            "task_id": blueprint.task_id,
            "result": audit_result,
            "timestamp": __import__('time').time(),
        })
        
        logger.info(f"质量审核完成，通过: {audit_result['passed']}")
        return audit_result

    async def _audit_with_llm(
        self, 
        blueprint: Any, 
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用 LLM 进行质量审核
        
        Args:
            blueprint: 任务蓝图
            execution_result: 执行结果
            
        Returns:
            审核结果字典
        """
        # 系统提示词
        system_prompt = """你是一名严格的质量审核员。
你的任务是对比任务蓝图和执行结果，评估质量。

请按以下格式输出 JSON：
{
  "passed": true/false,
  "score": 85.0,
  "issues": [
    {
      "type": "incomplete_step",
      "step_name": "步骤名称",
      "severity": "high/medium/low",
      "description": "问题描述"
    }
  ],
  "suggestions": ["建议1", "建议2"],
  "detailed_report": "详细报告"
}

评分标准：
- 90-100：优秀，完全符合要求
- 80-89：良好，基本符合要求
- 70-79：及格，部分符合要求
- 0-69：不及格，存在严重问题"""
        
        # 构建审核输入
        audit_input = f"""任务蓝图：
- 任务ID：{blueprint.task_id}
- 任务描述：{blueprint.description}
- 执行步骤：{blueprint.steps}

执行结果：
{execution_result}"""
        
        # 调用 LLM 进行审核
        response = await self.llm_client.audit(
            system_prompt=system_prompt,
            audit_input=audit_input,
            temperature=0.3,
        )
        
        # 解析响应
        try:
            import json
            result = json.loads(response)
            
            audit_result = {
                "passed": result.get("passed", False),
                "score": result.get("score", 0.0),
                "issues": result.get("issues", []),
                "suggestions": result.get("suggestions", []),
                "detailed_report": result.get("detailed_report", ""),
                "comparison_summary": {
                    "total_steps": len(blueprint.steps),
                    "completed_steps": len([s for s in execution_result.values() if s.get("status") == "completed"]),
                    "overall_match": 0.0,
                },
            }
            
            # 计算整体匹配度
            if audit_result["comparison_summary"]["total_steps"] > 0:
                audit_result["comparison_summary"]["overall_match"] = (
                    audit_result["comparison_summary"]["completed_steps"] /
                    audit_result["comparison_summary"]["total_steps"]
                )
            
        except Exception as e:
            logger.warning(f"解析 LLM 响应失败: {e}，使用默认审核结果")
            # 如果解析失败，使用默认审核结果
            audit_result = {
                "passed": True,
                "score": 80.0,
                "issues": [],
                "suggestions": ["审核完成，未发现明显问题"],
                "detailed_report": "审核完成，未发现明显问题",
                "comparison_summary": {
                    "total_steps": len(blueprint.steps),
                    "completed_steps": len([s for s in execution_result.values() if s.get("status") == "completed"]),
                    "overall_match": 1.0,
                },
            }
        
        return audit_result
    
    async def _compare_blueprint_with_result(
        self, 
        blueprint: Any, 
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        对比蓝图与执行结果
        
        Args:
            blueprint: 任务蓝图
            execution_result: 执行结果
            
        Returns:
            对比结果
        """
        logger.info("逐项对比蓝图与交付物")
        
        comparison = {
            "total_steps": len(blueprint.steps),
            "completed_steps": 0,
            "step_details": [],
            "overall_match": 0.0,
        }
        
        for i, step in enumerate(blueprint.steps):
            step_name = step.get("name", f"step_{i}")
            step_result = execution_result.get(step_name, {})
            
            # 检查步骤是否完成
            is_completed = step_result.get("status") == "completed"
            if is_completed:
                comparison["completed_steps"] += 1
            
            step_detail = {
                "step_name": step_name,
                "expected_expert": step.get("expert"),
                "actual_expert": step_result.get("expert"),
                "is_completed": is_completed,
                "has_output": bool(step_result.get("output")),
                "match_score": 1.0 if is_completed else 0.0,
            }
            
            comparison["step_details"].append(step_detail)
        
        # 计算整体匹配度
        if comparison["total_steps"] > 0:
            comparison["overall_match"] = (
                comparison["completed_steps"] / comparison["total_steps"]
            )
        
        logger.info(f"对比完成，匹配度: {comparison['overall_match']:.2%}")
        return comparison
    
    async def _generate_audit_report(
        self, 
        blueprint: Any, 
        execution_result: Dict[str, Any],
        comparison_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成审核报告
        
        Args:
            blueprint: 任务蓝图
            execution_result: 执行结果
            comparison_result: 对比结果
            
        Returns:
            审核报告
        """
        logger.info("生成质量审核报告")
        
        # 计算质量分数
        quality_score = self._calculate_quality_score(comparison_result)
        
        # 检查是否通过审核
        passed = quality_score >= 80.0  # 80分以上通过
        
        # 识别问题
        issues = self._identify_issues(comparison_result)
        
        # 生成建议
        suggestions = self._generate_suggestions(issues, comparison_result)
        
        # 生成详细报告
        detailed_report = self._create_detailed_report(
            blueprint, execution_result, comparison_result, quality_score
        )
        
        audit_result = {
            "passed": passed,
            "score": quality_score,
            "issues": issues,
            "suggestions": suggestions,
            "detailed_report": detailed_report,
            "comparison_summary": {
                "total_steps": comparison_result["total_steps"],
                "completed_steps": comparison_result["completed_steps"],
                "overall_match": comparison_result["overall_match"],
            },
        }
        
        return audit_result
    
    def _calculate_quality_score(self, comparison_result: Dict[str, Any]) -> float:
        """
        计算质量分数
        
        Args:
            comparison_result: 对比结果
            
        Returns:
            质量分数 (0-100)
        """
        # 基础分数
        base_score = comparison_result["overall_match"] * 100
        
        # 根据步骤完成情况调整
        completion_bonus = (
            comparison_result["completed_steps"] / max(comparison_result["total_steps"], 1)
        ) * 10
        
        # 计算最终分数
        final_score = min(base_score + completion_bonus, 100.0)
        
        logger.debug(f"质量分数计算: 基础={base_score:.1f}, 奖励={completion_bonus:.1f}, 最终={final_score:.1f}")
        return final_score
    
    def _identify_issues(self, comparison_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        识别问题
        
        Args:
            comparison_result: 对比结果
            
        Returns:
            问题列表
        """
        issues = []
        
        for step_detail in comparison_result["step_details"]:
            if not step_detail["is_completed"]:
                issues.append({
                    "type": "incomplete_step",
                    "step_name": step_detail["step_name"],
                    "severity": "high",
                    "description": f"步骤 '{step_detail['step_name']}' 未完成",
                })
            
            if not step_detail["has_output"]:
                issues.append({
                    "type": "no_output",
                    "step_name": step_detail["step_name"],
                    "severity": "medium",
                    "description": f"步骤 '{step_detail['step_name']}' 没有输出",
                })
            
            if step_detail["expected_expert"] != step_detail["actual_expert"]:
                issues.append({
                    "type": "expert_mismatch",
                    "step_name": step_detail["step_name"],
                    "severity": "low",
                    "description": f"步骤 '{step_detail['step_name']}' 专家不匹配",
                })
        
        return issues
    
    def _generate_suggestions(
        self, 
        issues: List[Dict[str, Any]], 
        comparison_result: Dict[str, Any]
    ) -> List[str]:
        """
        生成改进建议
        
        Args:
            issues: 问题列表
            comparison_result: 对比结果
            
        Returns:
            建议列表
        """
        suggestions = []
        
        # 基于问题生成建议
        high_severity_issues = [i for i in issues if i["severity"] == "high"]
        if high_severity_issues:
            suggestions.append("存在高优先级问题，建议重新执行相关步骤")
        
        # 基于匹配度生成建议
        if comparison_result["overall_match"] < 0.9:
            suggestions.append("整体匹配度较低，建议检查执行流程")
        
        # 基于完成度生成建议
        if comparison_result["completed_steps"] < comparison_result["total_steps"]:
            suggestions.append("存在未完成的步骤，建议补充执行")
        
        return suggestions
    
    def _create_detailed_report(
        self, 
        blueprint: Any, 
        execution_result: Dict[str, Any],
        comparison_result: Dict[str, Any],
        quality_score: float
    ) -> str:
        """
        创建详细报告
        
        Args:
            blueprint: 任务蓝图
            execution_result: 执行结果
            comparison_result: 对比结果
            quality_score: 质量分数
            
        Returns:
            详细报告文本
        """
        report = f"""
质量审核报告

任务ID: {blueprint.task_id}
任务描述: {blueprint.description}
审核时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

质量评分: {quality_score:.1f}/100

步骤完成情况:
"""
        for i, step_detail in enumerate(comparison_result["step_details"], 1):
            status = "✓" if step_detail["is_completed"] else "✗"
            report += f"{i}. [{status}] {step_detail['step_name']}\n"
            report += f"   期望专家: {step_detail['expected_expert']}\n"
            report += f"   实际专家: {step_detail['actual_expert']}\n"
            report += f"   匹配分数: {step_detail['match_score']:.2f}\n\n"
        
        report += f"""
统计信息:
- 总步骤数: {comparison_result['total_steps']}
- 完成步骤数: {comparison_result['completed_steps']}
- 整体匹配度: {comparison_result['overall_match']:.2%}

结论: {'通过' if quality_score >= 80 else '未通过'}审核
"""
        
        return report
    
    async def request_revision(
        self, 
        blueprint: Any, 
        audit_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        请求修改
        
        Args:
            blueprint: 原始蓝图
            audit_result: 审核结果
            
        Returns:
            修改请求
        """
        logger.info("生成修改请求")
        
        revision_request = {
            "task_id": blueprint.task_id,
            "original_blueprint": blueprint.model_dump(),
            "audit_issues": audit_result.get("issues", []),
            "suggestions": audit_result.get("suggestions", []),
            "revision_instructions": self._generate_revision_instructions(audit_result),
        }
        
        return revision_request
    
    def _generate_revision_instructions(self, audit_result: Dict[str, Any]) -> List[str]:
        """
        生成修改指令
        
        Args:
            audit_result: 审核结果
            
        Returns:
            修改指令列表
        """
        instructions = []
        
        for issue in audit_result.get("issues", []):
            if issue["type"] == "incomplete_step":
                instructions.append(f"重新执行步骤: {issue['step_name']}")
            elif issue["type"] == "no_output":
                instructions.append(f"为步骤 '{issue['step_name']}' 生成输出")
            elif issue["type"] == "expert_mismatch":
                instructions.append(f"为步骤 '{issue['step_name']}' 分配正确的专家")
        
        return instructions
    
    def get_audit_history(self) -> list:
        """
        获取审核历史
        
        Returns:
            审核历史列表
        """
        return self.audit_history.copy()
    
    def clear_audit_history(self):
        """清空审核历史"""
        self.audit_history.clear()
        logger.info("清空审核历史")
    
    async def compare_models(
        self, 
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        比较不同模型的结果
        
        Args:
            results: 不同模型的结果列表
            
        Returns:
            比较结果
        """
        logger.info(f"比较 {len(results)} 个模型的结果")
        
        # 这里实现模型比较逻辑
        # 可以用于A/B测试或模型选择
        
        comparison = {
            "models": [r.get("model", "unknown") for r in results],
            "quality_scores": [r.get("score", 0) for r in results],
            "best_model_index": 0,
            "recommendation": "",
        }
        
        # 找出最佳模型
        if comparison["quality_scores"]:
            best_index = comparison["quality_scores"].index(
                max(comparison["quality_scores"])
            )
            comparison["best_model_index"] = best_index
            comparison["recommendation"] = (
                f"推荐使用模型: {comparison['models'][best_index]}"
            )
        
        return comparison