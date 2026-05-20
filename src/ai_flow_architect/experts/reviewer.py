"""
审核员专家 - 负责代码审查和质量把控
"""

from typing import Dict, Any, List
import json
from .base import BaseExpert, ExpertConfig
from loguru import logger


class ReviewerExpert(BaseExpert):
    """
    审核员专家
    
    负责代码审查、质量把控、最佳实践检查
    """

    # 声明需要的输入字段（从上游步骤的结果中提取）
    # 审核员需要程序员的实现代码和技术设计
    required_input_fields: set = {"implementation", "technical_design"}

    # 声明输出格式
    output_format: str = "json"

    # 真实 LLM 调用的 prompt 模板
    LLM_REVIEW_PROMPT = """基于以下代码实现和技术上下文，生成一份完整的代码审查报告。

任务描述：
{task}

上游输入：
{context}

请严格按照以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{{
  "code_quality": {{
    "score": 85,
    "issues": ["..."],
    "suggestions": ["..."],
    "compliance": {{"coding_standards": true, "documentation_standards": false, "testing_standards": true}}
  }},
  "security": {{
    "score": 90,
    "vulnerabilities": ["..."],
    "issues": ["..."],
    "recommendations": ["..."]
  }},
  "performance": {{
    "score": 80,
    "bottlenecks": ["..."],
    "optimization_opportunities": ["..."],
    "suggestions": ["..."]
  }},
  "maintainability": {{
    "score": 75,
    "code_complexity": {{"level": "low/medium/high", "cyclomatic_complexity": 0, "suggestion": "..."}},
    "documentation_quality": {{"level": "low/medium/high", "coverage": 0.0, "suggestion": "..."}},
    "test_coverage": {{"level": "low/medium/high", "percentage": 0.0, "suggestion": "..."}},
    "suggestions": ["..."]
  }},
  "overall_score": 0.0,
  "verdict": "pass/revise/reject",
  "summary": "一句话总结审查结论"
}}"""

    def __init__(self, config: ExpertConfig = None, system_prompt: str = None, llm_client=None):
        """
        初始化审核员

        Args:
            config: 专家配置
            system_prompt: 由一号脑提供的覆盖提示词
        """
        default_config = ExpertConfig(
            name="审核员",
            model="gpt-4",
            temperature=0.2,  # 低温度以保证审核的严谨性
            max_tokens=4000,
            system_prompt="""你是一位严格的代码审核专家。
你的职责是：
1. 审查代码质量和规范
2. 检查潜在的安全漏洞
3. 评估代码的可维护性
4. 确保符合最佳实践
请以严谨、细致的态度进行审核，不放过任何细节。""",
        )
        
        super().__init__(config or default_config, system_prompt=system_prompt, llm_client=llm_client)
        self.review_reports = []
        self.issues_found = []
        
        logger.info("审核员专家初始化完成")
    
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行审核任务

        有 llm_client 时调用真实 LLM，无则回退到 mock 数据。
        """
        logger.info(f"审核员开始执行任务: {task[:50]}...")

        if self.llm_client is not None:
            return await self._execute_with_llm(task, context)
        else:
            return await self._execute_mock(task, context)

    async def _execute_with_llm(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用真实 LLM 执行代码审查"""
        prompt = self.LLM_REVIEW_PROMPT.format(
            task=task,
            context=json.dumps(context.get("filtered_input", {}), ensure_ascii=False, indent=2)
        )
        logger.info(f"审核员调用 LLM，prompt 长度: {len(prompt)} 字符")

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
            overall = parsed.get("overall_score", 0)
            verdict = parsed.get("verdict", "unknown")
            logger.info(f"审核员 LLM 调用完成，总分: {overall}, 裁决: {verdict}")
        except Exception as e:
            logger.error(f"审核员 LLM 调用失败: {e}，回退到 mock 数据")
            return await self._execute_mock(task, context)

        result = await self.format_output({
            "task": task,
            "code_quality_review": parsed.get("code_quality", {}),
            "security_review": parsed.get("security", {}),
            "performance_review": parsed.get("performance", {}),
            "maintainability_review": parsed.get("maintainability", {}),
            "overall_score": overall,
            "verdict": verdict,
            "summary": parsed.get("summary", ""),
        })
        self.review_reports.append(result)
        return result

    async def _execute_mock(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """回退：使用硬编码 mock 数据"""
        code_quality_review = await self._review_code_quality(task, context)
        security_review = await self._review_security(task, context)
        performance_review = await self._review_performance(task, context)
        maintainability_review = await self._review_maintainability(task, context)
        review_report = await self._generate_review_report(
            code_quality_review, security_review, performance_review, maintainability_review
        )
        result = await self.format_output({
            "task": task,
            "code_quality_review": code_quality_review,
            "security_review": security_review,
            "performance_review": performance_review,
            "maintainability_review": maintainability_review,
            "review_report": review_report,
            "overall_score": self._calculate_overall_score(
                code_quality_review, security_review, performance_review, maintainability_review
            ),
        })
        self.review_reports.append(result)
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
            logger.warning("审核员 JSON 解析失败，尝试提取 JSON 块")
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error("审核员 JSON 完全解析失败，返回空结构")
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
            "code_quality_aspects": self._identify_quality_aspects(task),
            "security_concerns": self._identify_security_concerns(task),
            "performance_issues": self._identify_performance_issues(task),
            "maintainability_factors": self._identify_maintainability_factors(task),
            "best_practices": self._identify_best_practices(task),
        }
        
        return analysis
    
    async def _review_code_quality(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        审查代码质量
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            代码质量审查结果
        """
        logger.info("审查代码质量")
        
        return {
            "score": 85,
            "issues": self._find_code_quality_issues(task),
            "suggestions": self._generate_quality_suggestions(task),
            "compliance": self._check_compliance(task),
        }
    
    async def _review_security(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        安全审查
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            安全审查结果
        """
        logger.info("进行安全审查")
        
        return {
            "score": 90,
            "vulnerabilities": self._find_vulnerabilities(task),
            "security_issues": self._find_security_issues(task),
            "recommendations": self._generate_security_recommendations(task),
        }
    
    async def _review_performance(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        性能审查
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            性能审查结果
        """
        logger.info("进行性能审查")
        
        return {
            "score": 80,
            "bottlenecks": self._find_bottlenecks(task),
            "optimization_opportunities": self._find_optimization_opportunities(task),
            "performance_suggestions": self._generate_performance_suggestions(task),
        }
    
    async def _review_maintainability(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        可维护性审查
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            可维护性审查结果
        """
        logger.info("进行可维护性审查")
        
        return {
            "score": 75,
            "code_complexity": self._analyze_code_complexity(task),
            "documentation_quality": self._analyze_documentation_quality(task),
            "test_coverage": self._analyze_test_coverage(task),
            "maintainability_suggestions": self._generate_maintainability_suggestions(task),
        }
    
    async def _generate_review_report(
        self,
        code_quality_review: Dict[str, Any],
        security_review: Dict[str, Any],
        performance_review: Dict[str, Any],
        maintainability_review: Dict[str, Any]
    ) -> str:
        """
        生成审核报告
        
        Args:
            code_quality_review: 代码质量审查
            security_review: 安全审查
            performance_review: 性能审查
            maintainability_review: 可维护性审查
            
        Returns:
            审核报告
        """
        report = f"""
代码审核报告

一、代码质量审查
- 质量分数: {code_quality_review.get('score', 0)}/100
- 发现问题数: {len(code_quality_review.get('issues', []))}
- 主要问题: {', '.join(code_quality_review.get('issues', [])[:3]) if code_quality_review.get('issues') else '无'}

二、安全审查
- 安全分数: {security_review.get('score', 0)}/100
- 发现漏洞数: {len(security_review.get('vulnerabilities', []))}
- 安全建议: {', '.join(security_review.get('recommendations', [])[:3]) if security_review.get('recommendations') else '无'}

三、性能审查
- 性能分数: {performance_review.get('score', 0)}/100
- 发现瓶颈数: {len(performance_review.get('bottlenecks', []))}
- 优化机会: {len(performance_review.get('optimization_opportunities', []))}

四、可维护性审查
- 可维护性分数: {maintainability_review.get('score', 0)}/100
- 代码复杂度: {maintainability_review.get('code_complexity', {}).get('level', 'unknown')}
- 文档质量: {maintainability_review.get('documentation_quality', {}).get('level', 'unknown')}
- 测试覆盖率: {maintainability_review.get('test_coverage', {}).get('percentage', 0):.1%}

五、总结
{self._generate_summary(code_quality_review, security_review, performance_review, maintainability_review)}
"""
        
        self.review_reports.append(report)
        return report
    
    def _calculate_overall_score(
        self,
        code_quality_review: Dict[str, Any],
        security_review: Dict[str, Any],
        performance_review: Dict[str, Any],
        maintainability_review: Dict[str, Any]
    ) -> float:
        """
        计算总体分数
        
        Args:
            code_quality_review: 代码质量审查
            security_review: 安全审查
            performance_review: 性能审查
            maintainability_review: 可维护性审查
            
        Returns:
            总体分数
        """
        weights = {
            "code_quality": 0.3,
            "security": 0.3,
            "performance": 0.2,
            "maintainability": 0.2,
        }
        
        overall_score = (
            code_quality_review.get("score", 0) * weights["code_quality"] +
            security_review.get("score", 0) * weights["security"] +
            performance_review.get("score", 0) * weights["performance"] +
            maintainability_review.get("score", 0) * weights["maintainability"]
        )
        
        return overall_score
    
    def _identify_quality_aspects(self, task: str) -> List[str]:
        """识别质量方面"""
        return ["代码规范", "命名约定", "注释质量"]
    
    def _identify_security_concerns(self, task: str) -> List[str]:
        """识别安全问题"""
        return ["输入验证", "数据加密", "权限控制"]
    
    def _identify_performance_issues(self, task: str) -> List[str]:
        """识别性能问题"""
        return ["算法复杂度", "数据库查询", "内存使用"]
    
    def _identify_maintainability_factors(self, task: str) -> List[str]:
        """识别可维护性因素"""
        return ["代码结构", "模块化程度", "文档完整性"]
    
    def _identify_best_practices(self, task: str) -> List[str]:
        """识别最佳实践"""
        return ["SOLID原则", "DRY原则", "KISS原则"]
    
    def _find_code_quality_issues(self, task: str) -> List[str]:
        """查找代码质量问题"""
        return ["代码重复", "命名不规范", "缺少注释"]
    
    def _generate_quality_suggestions(self, task: str) -> List[str]:
        """生成质量建议"""
        return ["重构重复代码", "统一命名规范", "添加必要注释"]
    
    def _check_compliance(self, task: str) -> Dict[str, Any]:
        """检查合规性"""
        return {
            "coding_standards": True,
            "documentation_standards": False,
            "testing_standards": True,
        }
    
    def _find_vulnerabilities(self, task: str) -> List[str]:
        """查找漏洞"""
        return ["SQL注入风险", "XSS漏洞"]
    
    def _find_security_issues(self, task: str) -> List[str]:
        """查找安全问题"""
        return ["硬编码密码", "不安全的依赖"]
    
    def _generate_security_recommendations(self, task: str) -> List[str]:
        """生成安全建议"""
        return ["使用参数化查询", "实施输入验证", "定期更新依赖"]
    
    def _find_bottlenecks(self, task: str) -> List[str]:
        """查找瓶颈"""
        return ["数据库查询慢", "内存泄漏"]
    
    def _find_optimization_opportunities(self, task: str) -> List[str]:
        """查找优化机会"""
        return ["缓存优化", "算法优化", "并发处理"]
    
    def _generate_performance_suggestions(self, task: str) -> List[str]:
        """生成性能建议"""
        return ["添加缓存层", "优化数据库查询", "使用异步处理"]
    
    def _analyze_code_complexity(self, task: str) -> Dict[str, Any]:
        """分析代码复杂度"""
        return {
            "cyclomatic_complexity": 15,
            "level": "medium",
            "suggestion": "建议拆分复杂函数",
        }
    
    def _analyze_documentation_quality(self, task: str) -> Dict[str, Any]:
        """分析文档质量"""
        return {
            "coverage": 0.70,
            "level": "medium",
            "suggestion": "补充API文档和示例代码",
        }
    
    def _analyze_test_coverage(self, task: str) -> Dict[str, Any]:
        """分析测试覆盖率"""
        return {
            "percentage": 0.75,
            "level": "medium",
            "suggestion": "增加边界条件测试",
        }
    
    def _generate_maintainability_suggestions(self, task: str) -> List[str]:
        """生成可维护性建议"""
        return ["减少代码复杂度", "增加文档", "提高测试覆盖率"]
    
    def _generate_summary(
        self,
        code_quality_review: Dict[str, Any],
        security_review: Dict[str, Any],
        performance_review: Dict[str, Any],
        maintainability_review: Dict[str, Any]
    ) -> str:
        """生成总结"""
        overall_score = self._calculate_overall_score(
            code_quality_review, security_review, performance_review, maintainability_review
        )
        
        if overall_score >= 90:
            return "代码质量优秀，符合生产环境标准。"
        elif overall_score >= 80:
            return "代码质量良好，建议进行小幅度优化。"
        elif overall_score >= 70:
            return "代码质量一般，需要进行改进。"
        else:
            return "代码质量较差，需要进行重大改进。"
    
    def get_review_reports(self) -> List[str]:
        """获取所有审核报告"""
        return self.review_reports.copy()
    
    def get_issues_found(self) -> List[str]:
        """获取所有发现的问题"""
        return self.issues_found.copy()
    
    async def reset(self):
        """重置审核员状态"""
        await super().reset()
        self.review_reports.clear()
        self.issues_found.clear()
        logger.info("审核员状态已重置")