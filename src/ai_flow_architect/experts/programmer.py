"""
程序员专家 - 负责代码实现
"""

from typing import Dict, Any, List
import json
from .base import BaseExpert, ExpertConfig
from loguru import logger


class ProgrammerExpert(BaseExpert):
    """
    程序员专家

    负责代码实现、技术方案设计、代码优化
    """

    # 声明需要的输入字段（从上游步骤的结果中提取）
    # 程序员需要评估师的可行性评估和技术方案
    required_input_fields: set = {"feasibility_assessment", "evaluation_report"}

    # 声明输出格式
    output_format: str = "code"

    # 真实 LLM 调用的 prompt 模板
    LLM_PROGRAMMER_PROMPT = """基于以下任务描述和上游分析结果，编写完整的代码实现。

任务描述：
{task}

上游评估与设计方案：
{context}

请严格按照以下 JSON 格式返回（不要包含 markdown 代码块标记，代码放在字符串字段中）：
{{
  "technical_analysis": {{
    "architecture_pattern": "...",
    "design_patterns": ["..."],
    "technology_stack": {{"backend": "...", "database": "...", "cache": "...", "queue": "..."}},
    "api_design": {{"rest_endpoints": ["..."], "authentication": "..."}},
    "data_model": {{"entities": ["..."], "relationships": ["..."]}}
  }},
  "implementation": {{
    "main_module": "完整的代码实现放在这里",
    "supporting_modules": ["..."],
    "dependencies": ["..."],
    "entry_point": "..."
  }},
  "tests": ["..."],
  "code_quality_metrics": {{
    "complexity_score": 0.0,
    "maintainability_score": 0.0,
    "test_coverage": 0.0,
    "documentation_coverage": 0.0
  }},
  "notes": "架构决策说明和注意事项"
}}"""

    def __init__(self, config: ExpertConfig = None, system_prompt: str = None, llm_client=None):
        """
        初始化程序员

        Args:
            config: 专家配置
            system_prompt: 由一号脑提供的覆盖提示词
        """
        default_config = ExpertConfig(
            name="程序员",
            model="gpt-4",
            temperature=0.4,  # 适中温度，平衡创意和准确性
            max_tokens=8000,  # 代码生成需要更多Token
            system_prompt="""你是一位资深的软件开发工程师。
你的职责是：
1. 根据需求设计技术方案
2. 编写高质量、可维护的代码
3. 进行代码优化和重构
4. 解决技术难题
请遵循最佳实践，编写清晰、高效的代码。""",
        )
        
        super().__init__(config or default_config, system_prompt=system_prompt, llm_client=llm_client)
        self.code_snippets = []
        self.technical_decisions = []
        
        logger.info("程序员专家初始化完成")
    
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行编程任务

        有 llm_client 时调用真实 LLM，无则回退到 mock 数据。
        """
        logger.info(f"程序员开始执行任务: {task[:50]}...")

        if self.llm_client is not None:
            return await self._execute_with_llm(task, context)
        else:
            return await self._execute_mock(task, context)

    async def _execute_with_llm(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用真实 LLM 生成代码"""
        prompt = self.LLM_PROGRAMMER_PROMPT.format(
            task=task,
            context=json.dumps(context.get("filtered_input", {}), ensure_ascii=False, indent=2)
        )
        logger.info(f"程序员调用 LLM，prompt 长度: {len(prompt)} 字符")

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
            logger.info("程序员 LLM 调用完成")
        except Exception as e:
            logger.error(f"程序员 LLM 调用失败: {e}，回退到 mock 数据")
            return await self._execute_mock(task, context)

        result = await self.format_output({
            "task": task,
            "technical_analysis": parsed.get("technical_analysis", {}),
            "technical_design": parsed.get("technical_analysis", {}),
            "implementation": parsed.get("implementation", {}),
            "code_quality_metrics": parsed.get("code_quality_metrics", {}),
            "notes": parsed.get("notes", ""),
        })
        self.code_snippets.append(result)
        return result

    async def _execute_mock(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """回退：使用硬编码 mock 数据"""
        technical_analysis = await self._analyze_technical_requirements(task, context)
        technical_design = await self._design_technical_solution(technical_analysis)
        implementation = await self._implement_code(technical_design, context)
        optimized_code = await self._optimize_code(implementation)
        result = await self.format_output({
            "task": task,
            "technical_analysis": technical_analysis,
            "technical_design": technical_design,
            "implementation": optimized_code,
            "code_quality_metrics": self._calculate_code_quality(optimized_code),
        })
        self.code_snippets.append(result)
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
            logger.warning("程序员 JSON 解析失败，尝试提取 JSON 块")
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error("程序员 JSON 完全解析失败，返回空结构")
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
            "technical_requirements": self._extract_technical_requirements(task),
            "programming_language": self._determine_language(task, context),
            "complexity_estimate": self._estimate_complexity(task),
            "dependencies": self._identify_dependencies(task, context),
            "implementation_approach": self._suggest_approach(task),
        }
        
        return analysis
    
    async def _analyze_technical_requirements(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析技术需求
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            技术需求分析
        """
        logger.info("分析技术需求")
        
        return {
            "functional_requirements": self._extract_functional_requirements(task),
            "performance_requirements": self._extract_performance_requirements(task),
            "security_requirements": self._extract_security_requirements(task),
            "scalability_requirements": self._extract_scalability_requirements(task),
            "integration_requirements": self._extract_integration_requirements(task, context),
        }
    
    async def _design_technical_solution(self, technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        设计技术方案
        
        Args:
            technical_analysis: 技术需求分析
            
        Returns:
            技术设计方案
        """
        logger.info("设计技术方案")
        
        return {
            "architecture_pattern": self._select_architecture_pattern(technical_analysis),
            "design_patterns": self._select_design_patterns(technical_analysis),
            "technology_stack": self._select_technology_stack(technical_analysis),
            "api_design": self._design_api(technical_analysis),
            "data_model": self._design_data_model(technical_analysis),
        }
    
    async def _implement_code(self, technical_design: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        实现代码
        
        Args:
            technical_design: 技术设计
            context: 上下文信息
            
        Returns:
            实现结果
        """
        logger.info("实现代码")
        
        # 这里应该生成实际的代码
        # 目前返回模拟结果
        
        implementation = {
            "main_module": self._generate_main_module(technical_design),
            "supporting_modules": self._generate_supporting_modules(technical_design),
            "tests": self._generate_tests(technical_design),
            "documentation": self._generate_documentation(technical_design),
        }
        
        self.code_snippets.append(implementation)
        return implementation
    
    async def _optimize_code(self, implementation: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化代码
        
        Args:
            implementation: 实现结果
            
        Returns:
            优化后的代码
        """
        logger.info("优化代码")
        
        # 这里应该进行代码优化
        # 目前返回原实现
        
        optimized = implementation.copy()
        optimized["optimizations_applied"] = [
            "性能优化",
            "代码简化",
            "错误处理增强",
        ]
        
        return optimized
    
    def _extract_technical_requirements(self, task: str) -> List[str]:
        """提取技术需求"""
        return ["高性能", "可扩展", "安全性"]
    
    def _determine_language(self, task: str, context: Dict[str, Any]) -> str:
        """确定编程语言"""
        task_lower = task.lower()
        
        if "python" in task_lower or "数据" in task_lower or "ai" in task_lower:
            return "Python"
        elif "web" in task_lower or "前端" in task_lower:
            return "JavaScript/TypeScript"
        elif "移动" in task_lower or "app" in task_lower:
            return "Kotlin/Swift"
        else:
            return "Python"  # 默认使用Python
    
    def _estimate_complexity(self, task: str) -> str:
        """估算复杂度"""
        return "medium"
    
    def _identify_dependencies(self, task: str, context: Dict[str, Any]) -> List[str]:
        """识别依赖"""
        return ["核心框架", "第三方库"]
    
    def _suggest_approach(self, task: str) -> str:
        """建议实现方法"""
        return "迭代开发"
    
    def _extract_functional_requirements(self, task: str) -> List[str]:
        """提取功能需求"""
        return ["核心功能", "辅助功能"]
    
    def _extract_performance_requirements(self, task: str) -> List[str]:
        """提取性能需求"""
        return ["响应时间<100ms", "支持1000并发"]
    
    def _extract_security_requirements(self, task: str) -> List[str]:
        """提取安全需求"""
        return ["数据加密", "身份验证"]
    
    def _extract_scalability_requirements(self, task: str) -> List[str]:
        """提取可扩展性需求"""
        return ["水平扩展", "模块化设计"]
    
    def _extract_integration_requirements(self, task: str, context: Dict[str, Any]) -> List[str]:
        """提取集成需求"""
        return ["API集成", "数据库集成"]
    
    def _select_architecture_pattern(self, technical_analysis: Dict[str, Any]) -> str:
        """选择架构模式"""
        return "微服务架构"
    
    def _select_design_patterns(self, technical_analysis: Dict[str, Any]) -> List[str]:
        """选择设计模式"""
        return ["工厂模式", "观察者模式", "策略模式"]
    
    def _select_technology_stack(self, technical_analysis: Dict[str, Any]) -> Dict[str, str]:
        """选择技术栈"""
        return {
            "backend": "Python/FastAPI",
            "database": "PostgreSQL",
            "cache": "Redis",
            "queue": "RabbitMQ",
        }
    
    def _design_api(self, technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """设计API"""
        return {
            "rest_endpoints": ["/api/v1/resource"],
            "graphql_schema": None,
            "authentication": "JWT",
        }
    
    def _design_data_model(self, technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """设计数据模型"""
        return {
            "entities": ["User", "Resource", "Task"],
            "relationships": ["User-Resource: 1:N", "Resource-Task: 1:N"],
        }
    
    def _generate_main_module(self, technical_design: Dict[str, Any]) -> str:
        """生成主模块代码"""
        return """
# Main Module
class MainApplication:
    def __init__(self):
        self.config = self.load_config()
        self.initialize_components()
    
    def run(self):
        # 应用启动逻辑
        pass
"""
    
    def _generate_supporting_modules(self, technical_design: Dict[str, Any]) -> List[str]:
        """生成辅助模块代码"""
        return ["config.py", "utils.py", "exceptions.py"]
    
    def _generate_tests(self, technical_design: Dict[str, Any]) -> List[str]:
        """生成测试代码"""
        return ["test_main.py", "test_integration.py"]
    
    def _generate_documentation(self, technical_design: Dict[str, Any]) -> str:
        """生成文档"""
        return "# 技术文档\n\n## 架构设计\n\n..."
    
    def _calculate_code_quality(self, code: Dict[str, Any]) -> Dict[str, Any]:
        """计算代码质量指标"""
        return {
            "complexity_score": 0.8,
            "maintainability_score": 0.85,
            "test_coverage": 0.75,
            "documentation_coverage": 0.70,
        }
    
    def get_code_snippets(self) -> List[Dict[str, Any]]:
        """获取所有代码片段"""
        return self.code_snippets.copy()
    
    def get_technical_decisions(self) -> List[Dict[str, Any]]:
        """获取所有技术决策"""
        return self.technical_decisions.copy()
    
    async def reset(self):
        """重置程序员状态"""
        await super().reset()
        self.code_snippets.clear()
        self.technical_decisions.clear()
        logger.info("程序员状态已重置")