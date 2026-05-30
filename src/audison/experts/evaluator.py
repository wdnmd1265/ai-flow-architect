"""
评估师专家 - 负责需求分析和评估
"""

from typing import Dict, Any, List
import json
from .base import BaseExpert, ExpertConfig
from loguru import logger


class EvaluatorExpert(BaseExpert):
    """
    评估师专家

    负责需求分析、可行性评估、风险评估
    """

    # 声明需要的输入字段（从上游步骤的结果中提取）
    # 评估师是首步，不需要上游字段，只接收原始任务描述
    required_input_fields: set = set()

    # 声明输出格式
    output_format: str = "json"

    # 真实 LLM 调用的 prompt 模板
    LLM_EVALUATE_PROMPT = """基于以下任务描述和执行上下文，生成一份完整的评估报告。

任务描述：
{task}

上下文：
{context}

请严格按照以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{{
  "requirement_analysis": {{
    "functional_requirements": ["..."],
    "non_functional_requirements": ["..."],
    "constraints": ["..."],
    "assumptions": ["..."],
    "dependencies": ["..."],
    "clarity_score": 0.0
  }},
  "feasibility_assessment": {{
    "technical_score": 0.0,
    "economic_score": 0.0,
    "schedule_score": 0.0,
    "overall_score": 0.0,
    "technical_challenges": ["..."]
  }},
  "risk_assessment": {{
    "risks": [
      {{"type": "technical/resource/schedule", "description": "...", "level": "low/medium/high", "probability": 0.0, "impact": "low/medium/high"}}
    ],
    "overall_risk": "low/medium/high",
    "mitigation_strategies": ["..."]
  }},
  "summary": "一句话总结评估结论",
  "recommendation": "建议：go/review/reject"
}}"""

    def __init__(self, config: ExpertConfig = None, system_prompt: str = None, llm_client=None):
        """
        初始化评估师

        Args:
            config: 专家配置
            system_prompt: 由一号脑提供的覆盖提示词
            llm_client: LLM 客户端实例（可选）
        """
        default_config = ExpertConfig(
            name="评估师",
            model="gpt-4",
            temperature=0.3,  # 较低温度以保证评估的准确性
            max_tokens=4000,
            system_prompt="""你是一位严谨的评估分析师。
你的职责是：
1. 深入分析需求，识别潜在问题
2. 评估技术方案的可行性
3. 识别项目风险并提出缓解措施
4. 提供数据驱动的决策支持
请以客观、严谨的态度进行评估。""",
        )
        
        super().__init__(config or default_config, system_prompt=system_prompt, llm_client=llm_client)
        self.evaluations = []
        
        logger.info("评估师专家初始化完成")
    
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行评估任务

        有 llm_client 时调用真实 LLM，无则回退到 mock 数据。
        """
        logger.info(f"评估师开始执行任务: {task[:50]}...")

        if self.llm_client is not None:
            return await self._execute_with_llm(task, context)
        else:
            return await self._execute_mock(task, context)

    async def _execute_with_llm(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用真实 LLM 执行评估"""
        prompt = self.LLM_EVALUATE_PROMPT.format(
            task=task,
            context=json.dumps(context.get("filtered_input", {}), ensure_ascii=False, indent=2)
        )
        logger.info(f"评估师调用 LLM，prompt 长度: {len(prompt)} 字符")

        try:
            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": self.config.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            parsed = self._parse_json_response(response)
            logger.info(f"评估师 LLM 调用完成，整体风险: {parsed.get('risk_assessment', {}).get('overall_risk', 'unknown')}")
        except Exception as e:
            logger.error(f"评估师 LLM 调用失败: {e}，回退到 mock 数据")
            return await self._execute_mock(task, context)

        result = await self.format_output({
            "task": task,
            "requirement_analysis": parsed.get("requirement_analysis", {}),
            "feasibility_assessment": parsed.get("feasibility_assessment", {}),
            "risk_assessment": parsed.get("risk_assessment", {}),
            "summary": parsed.get("summary", ""),
            "recommendation": parsed.get("recommendation", ""),
        })
        self.evaluations.append(result)
        return result

    async def _execute_mock(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """回退：使用硬编码 mock 数据"""
        requirement_analysis = await self._analyze_requirements(task, context)
        feasibility_assessment = await self._assess_feasibility(task, context)
        risk_assessment = await self._assess_risks(task, context)
        evaluation_report = await self._generate_report(
            requirement_analysis, feasibility_assessment, risk_assessment
        )
        result = await self.format_output({
            "task": task,
            "requirement_analysis": requirement_analysis,
            "feasibility_assessment": feasibility_assessment,
            "risk_assessment": risk_assessment,
            "evaluation_report": evaluation_report,
        })
        self.evaluations.append(result)
        return result

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON，带容错"""
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("评估师 JSON 解析失败，尝试提取 JSON 块")
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error("评估师 JSON 完全解析失败，返回空结构")
            return {}
    
    async def analyze(self, input_data: Any) -> Dict[str, Any]:
        """
        分析输入数据
        
        Args:
            input_data: 输入数据
            
        Returns:
            分析结果
        """
        task = input_data.get("task", "")
        context = input_data.get("context", {})
        
        analysis = {
            "requirement_clarity": self._assess_requirement_clarity(task),
            "technical_complexity": self._assess_technical_complexity(task, context),
            "resource_requirements": self._estimate_resources(task),
            "timeline_estimate": self._estimate_timeline(task),
            "success_probability": self._estimate_success_probability(task, context),
        }
        
        return analysis
    
    async def _analyze_requirements(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析需求
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            需求分析结果
        """
        logger.info("分析需求")
        
        return {
            "functional_requirements": self._extract_functional_requirements(task),
            "non_functional_requirements": self._extract_non_functional_requirements(task),
            "constraints": context.get("constraints", []),
            "assumptions": self._identify_assumptions(task),
            "dependencies": self._identify_dependencies(task, context),
        }
    
    async def _assess_feasibility(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估可行性
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            可行性评估结果
        """
        logger.info("评估可行性")
        
        technical_feasibility = self._assess_technical_feasibility(task, context)
        economic_feasibility = self._assess_economic_feasibility(task)
        schedule_feasibility = self._assess_schedule_feasibility(task)
        
        return {
            "technical_feasibility": technical_feasibility,
            "economic_feasibility": economic_feasibility,
            "schedule_feasibility": schedule_feasibility,
            "overall_feasibility": (
                technical_feasibility["score"] * 0.5 +
                economic_feasibility["score"] * 0.3 +
                schedule_feasibility["score"] * 0.2
            ),
        }
    
    async def _assess_risks(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估风险
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            风险评估结果
        """
        logger.info("评估风险")
        
        risks = []
        
        # 技术风险
        technical_risks = self._identify_technical_risks(task, context)
        risks.extend(technical_risks)
        
        # 资源风险
        resource_risks = self._identify_resource_risks(task)
        risks.extend(resource_risks)
        
        # 时间风险
        schedule_risks = self._identify_schedule_risks(task)
        risks.extend(schedule_risks)
        
        # 计算整体风险等级
        risk_levels = [r["level"] for r in risks]
        overall_risk = "high" if "high" in risk_levels else (
            "medium" if "medium" in risk_levels else "low"
        )
        
        return {
            "risks": risks,
            "overall_risk": overall_risk,
            "risk_mitigation_strategies": self._generate_mitigation_strategies(risks),
        }
    
    async def _generate_report(
        self,
        requirement_analysis: Dict[str, Any],
        feasibility_assessment: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> str:
        """
        生成评估报告
        
        Args:
            requirement_analysis: 需求分析
            feasibility_assessment: 可行性评估
            risk_assessment: 风险评估
            
        Returns:
            评估报告
        """
        report = f"""
评估报告

一、需求分析
- 功能需求数量: {len(requirement_analysis.get('functional_requirements', []))}
- 非功能需求数量: {len(requirement_analysis.get('non_functional_requirements', []))}
- 约束条件数量: {len(requirement_analysis.get('constraints', []))}

二、可行性评估
- 技术可行性: {feasibility_assessment.get('technical_feasibility', {}).get('score', 0):.2f}
- 经济可行性: {feasibility_assessment.get('economic_feasibility', {}).get('score', 0):.2f}
- 时间可行性: {feasibility_assessment.get('schedule_feasibility', {}).get('score', 0):.2f}
- 综合可行性: {feasibility_assessment.get('overall_feasibility', 0):.2f}

三、风险评估
- 风险数量: {len(risk_assessment.get('risks', []))}
- 整体风险等级: {risk_assessment.get('overall_risk', 'unknown')}

四、建议
{self._generate_recommendations(feasibility_assessment, risk_assessment)}
"""
        return report
    
    def _assess_requirement_clarity(self, task: str) -> Dict[str, Any]:
        """评估需求清晰度"""
        return {
            "score": 0.8,
            "clarity_level": "high",
            "ambiguities": [],
        }
    
    def _assess_technical_complexity(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """评估技术复杂度"""
        return {
            "score": 0.7,
            "complexity_level": "medium",
            "complex_factors": [],
        }
    
    def _estimate_resources(self, task: str) -> Dict[str, Any]:
        """估算资源需求"""
        return {
            "human_resources": "中等",
            "computational_resources": "标准",
            "time_estimate": "2-4周",
        }
    
    def _estimate_timeline(self, task: str) -> Dict[str, Any]:
        """估算时间线"""
        return {
            "minimum_duration": "2周",
            "expected_duration": "4周",
            "maximum_duration": "8周",
        }
    
    def _estimate_success_probability(self, task: str, context: Dict[str, Any]) -> float:
        """估算成功概率"""
        return 0.85
    
    def _extract_functional_requirements(self, task: str) -> List[str]:
        """提取功能需求"""
        return ["核心功能实现", "用户界面设计", "数据处理逻辑"]
    
    def _extract_non_functional_requirements(self, task: str) -> List[str]:
        """提取非功能需求"""
        return ["性能要求", "安全要求", "可维护性"]
    
    def _identify_assumptions(self, task: str) -> List[str]:
        """识别假设条件"""
        return ["用户具备基本技术背景", "开发环境稳定"]
    
    def _identify_dependencies(self, task: str, context: Dict[str, Any]) -> List[str]:
        """识别依赖关系"""
        return ["外部API可用性", "第三方库支持"]
    
    def _assess_technical_feasibility(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """评估技术可行性"""
        return {
            "score": 0.9,
            "feasibility_level": "high",
            "technical_challenges": [],
        }
    
    def _assess_economic_feasibility(self, task: str) -> Dict[str, Any]:
        """评估经济可行性"""
        return {
            "score": 0.8,
            "feasibility_level": "high",
            "cost_estimate": "中等",
        }
    
    def _assess_schedule_feasibility(self, task: str) -> Dict[str, Any]:
        """评估时间可行性"""
        return {
            "score": 0.7,
            "feasibility_level": "medium",
            "timeline_risks": [],
        }
    
    def _identify_technical_risks(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别技术风险"""
        return [
            {
                "type": "technical",
                "description": "技术实现复杂度",
                "level": "medium",
                "probability": 0.3,
                "impact": "medium",
            }
        ]
    
    def _identify_resource_risks(self, task: str) -> List[Dict[str, Any]]:
        """识别资源风险"""
        return [
            {
                "type": "resource",
                "description": "资源不足风险",
                "level": "low",
                "probability": 0.2,
                "impact": "low",
            }
        ]
    
    def _identify_schedule_risks(self, task: str) -> List[Dict[str, Any]]:
        """识别时间风险"""
        return [
            {
                "type": "schedule",
                "description": "时间延误风险",
                "level": "medium",
                "probability": 0.4,
                "impact": "medium",
            }
        ]
    
    def _generate_mitigation_strategies(self, risks: List[Dict[str, Any]]) -> List[str]:
        """生成风险缓解策略"""
        strategies = []
        for risk in risks:
            if risk["level"] == "high":
                strategies.append(f"针对 {risk['type']} 风险，建议制定详细应对计划")
            elif risk["level"] == "medium":
                strategies.append(f"针对 {risk['type']} 风险，建议加强监控和预警")
        return strategies
    
    def _generate_recommendations(
        self,
        feasibility_assessment: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> str:
        """生成建议"""
        recommendations = []
        
        if feasibility_assessment.get("overall_feasibility", 0) < 0.7:
            recommendations.append("建议重新评估项目范围或技术方案")
        
        if risk_assessment.get("overall_risk") == "high":
            recommendations.append("建议制定详细的风险管理计划")
        
        if not recommendations:
            recommendations.append("项目可行性良好，建议按计划推进")
        
        return "\n".join([f"- {rec}" for rec in recommendations])
    
    def get_evaluations(self) -> List[Dict[str, Any]]:
        """获取所有评估结果"""
        return self.evaluations.copy()
    
    async def reset(self):
        """重置评估师状态"""
        await super().reset()
        self.evaluations.clear()
        logger.info("评估师状态已重置")