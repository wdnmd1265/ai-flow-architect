"""
盲审脑 - 无上下文终审

独立审查者，不接收 BrainOne/BrainTwo 的任何论据，
只接收原始 requirement + ai_output，防止锚定效应（anchoring bias）。

基于 ARIS 论文：终审者看过前面审查者的论据后会被锚定，无法独立判断。
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from ..utils.llm_client import LLMClient


class BlindVerdict(BaseModel):
    """盲审独立判决"""
    verdict: str = Field(..., description="结论：pass / review / reject")
    score: float = Field(0.0, description="质量分数 (0-100)")
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="发现的问题")
    rationale: str = Field("", description="判决理由")


class BrainBlind:
    """
    盲审脑 - 无上下文终审。

    关键设计：
    - 不接收任何先前的审查结果或论据
    - 只接收原始 requirement + ai_output
    - 使用不同于主审查模型的 LLM 实例
    - 返回独立的 BlindVerdict
    """

    # 盲审系统提示词（精简，不引导审查看其他结果）
    BLIND_AUDIT_PROMPT = """你是一名独立的盲审审查员。

你的任务：仅基于以下需求描述和 AI 产出，给出独立的判决。

重要：你没有看过任何其他人的审查结果，你的判断必须完全独立。

审查维度：
1. 需求匹配度：产出是否完整实现了需求中描述的功能
2. 安全性：是否存在安全漏洞（SQL 注入、XSS、硬编码密钥等）
3. 逻辑正确性：逻辑是否正确，边界条件是否处理
4. 副作用：是否引入了需求中没提到的副作用

请严格按照以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{
  "verdict": "pass/review/reject",
  "score": 85.0,
  "findings": [
    {
      "type": "security/logic/performance/missing",
      "severity": "high/medium/low",
      "description": "具体的问题描述"
    }
  ],
  "rationale": "你的判决理由，简要说明为什么给出这个结论"
}

评分标准：
- 90-100：优秀，完全符合需求
- 80-89：良好，基本符合需求
- 70-79：及格，部分符合需求
- 0-69：不及格，存在严重问题

verdict:
- pass：整体质量良好，可以信任
- review：存在需要关注的问题，建议人工审查
- reject：存在严重缺陷，不应直接使用"""

    def __init__(self, model: str):
        """
        初始化盲审脑。

        Args:
            model: 盲审使用的模型（应与主审查模型不同）
        """
        self.model = model
        self.llm_client = LLMClient(model)
        logger.info(f"盲审脑初始化完成 | 模型: {model}")

    async def audit(
        self,
        requirement: str,
        ai_output: str,
    ) -> BlindVerdict:
        """
        执行盲审——纯独立审查。

        Args:
            requirement: 用户需求描述
            ai_output: AI 生成的产出

        Returns:
            BlindVerdict 独立判决结果
        """
        logger.info(f"盲审开始 | 模型: {self.model} | 需求长度: {len(requirement)} | 产出长度: {len(ai_output)}")

        # 截断过长的产出
        truncated_output = ai_output[:3000] + "..." if len(ai_output) > 3000 else ai_output

        audit_input = f"需求：\n{requirement}\n\nAI 产出：\n{truncated_output}"

        try:
            response = await self.llm_client.audit(
                system_prompt=self.BLIND_AUDIT_PROMPT,
                audit_input=audit_input,
                temperature=0.3,
            )

            # 解析 JSON 响应
            text = response.strip() if isinstance(response, str) else response.get("content", "")
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
                if text.endswith("```"):
                    text = text[:-3]

            result = json.loads(text)
            verdict = BlindVerdict(
                verdict=result.get("verdict", "review"),
                score=float(result.get("score", 50)),
                findings=result.get("findings", []),
                rationale=result.get("rationale", ""),
            )
            logger.info(f"盲审完成 | 结论: {verdict.verdict} | 分数: {verdict.score:.1f}")
            return verdict

        except json.JSONDecodeError as e:
            logger.warning(f"盲审 JSON 解析失败: {e}，使用降级结果")
            return BlindVerdict(
                verdict="review",
                score=50.0,
                findings=[{
                    "type": "audit_error",
                    "severity": "high",
                    "description": "Blind review returned non-JSON response"
                }],
                rationale="盲审模型返回非 JSON 格式，降级为 review",
            )
        except Exception as e:
            logger.error(f"盲审失败: {e}", exc_info=True)
            return BlindVerdict(
                verdict="review",
                score=0.0,
                findings=[{
                    "type": "audit_error",
                    "severity": "high",
                    "description": f"Blind review failed: {str(e)}"
                }],
                rationale=f"盲审过程异常: {str(e)}",
            )

    def _load_models_config(self) -> Dict[str, Any]:
        """加载 models.yaml 配置文件。"""
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"加载 models.yaml 失败: {e}，使用空配置")
            return {}

    def _check_api_key(self, model: str) -> bool:
        """检查模型对应的 API key 是否存在。"""
        import os
        key_map = {
            "gpt-": "OPENAI_API_KEY",
            "claude-": "ANTHROPIC_API_KEY",
            "deepseek-": "DEEPSEEK_API_KEY",
            "qwen-": "DASHSCOPE_API_KEY",
            "glm-": "ZHIPU_API_KEY",
            "moonshot-": "MOONSHOT_API_KEY",
        }
        for prefix, env_var in key_map.items():
            if model.startswith(prefix):
                return bool(os.getenv(env_var))
        return False