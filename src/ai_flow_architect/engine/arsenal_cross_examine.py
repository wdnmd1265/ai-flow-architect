"""
跨审查武器（Cross-examine）

输入 AI 生成的文本 + 原始需求，用不同模型重新回答同一需求，
进行句子级差异分析，四标签分类分歧点。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from ..utils.arsenal_client import ArsenalClient, CrossExamineResult


@dataclass
class CrossExamineConfig:
    """跨审查配置"""
    models: List[str] = field(default_factory=list)
    allow_single_provider: bool = False
    line_range: Optional[Tuple[int, int]] = None
    output_format: str = "text"  # text / html / json


class CrossExamineEngine:
    """
    跨审查引擎
    
    核心功能：
    1. 读取 output.txt 和原始需求
    2. 用不同模型重新回答同一需求
    3. 句子级差异分析
    4. 四标签分类分歧点
    """
    
    def __init__(
        self, 
        models: Optional[List[str]] = None,
        allow_single_provider: bool = False,
    ):
        self.config = CrossExamineConfig(
            models=models or [],
            allow_single_provider=allow_single_provider,
        )
        self.client = None
    
    def _init_client(self):
        """延迟初始化 ArsenalClient（避免测试时立即需要 API key）"""
        if self.client is not None:
            return
        if self.config.models:
            self.client = ArsenalClient(
                models=self.config.models,
                allow_single_provider=self.config.allow_single_provider,
            )
        else:
            self.client = ArsenalClient(
                model="gpt-4o-mini",
                allow_single_provider=self.config.allow_single_provider,
            )
    
    async def run(
        self,
        output_text: str,
        requirement: str,
        line_range: Optional[Tuple[int, int]] = None,
    ) -> CrossExamineResult:
        """
        执行跨审查
        
        Args:
            output_text: AI 生成的文本
            requirement: 原始需求
            line_range: 可选，仅审查指定行范围
            
        Returns:
            CrossExamineResult
        """
        logger.info(f"开始跨审查 | 需求长度: {len(requirement)} | 输出长度: {len(output_text)}")
        
        if line_range:
            # 提取指定行范围
            lines = output_text.splitlines()
            start, end = line_range
            if start < 0 or end > len(lines):
                raise ValueError(f"行范围 {line_range} 超出文本范围 (0-{len(lines)})")
            output_text = "\n".join(lines[start:end])
            logger.info(f"限制审查行范围: {start}-{end}")
        
        # 延迟初始化客户端
        self._init_client()
        result = await self.client.cross_examine(
            requirement=requirement,
            output=output_text,
            line_range=line_range,
        )
        
        logger.info(f"跨审查完成 | 分歧点: {len(result.divergences)} | 一致: {result.agreement}")
        return result
    
    def format_result(
        self,
        result: CrossExamineResult,
        format_type: str = "text",
    ) -> str:
        """
        格式化跨审查结果
        
        Args:
            result: CrossExamineResult
            format_type: text / html / json
            
        Returns:
            格式化后的字符串
        """
        if format_type == "json":
            import json
            return json.dumps({
                "original_output": result.original_output,
                "second_output": result.second_output,
                "divergences": result.divergences,
                "agreement": result.agreement,
                "single_provider": result.single_provider,
                "provider_warning": result.provider_warning,
                "models_used": result.models_used,
                "trust_level": result.trust_level,
                "confirmed_count": result.confirmed_count,
                "disputed_count": result.disputed_count,
                "blind_spot_count": result.blind_spot_count,
                "hallucination_count": result.hallucination_count,
            }, ensure_ascii=False, indent=2)
        
        elif format_type == "html":
            return self._format_html(result)
        
        else:  # text
            return self._format_text(result)
    
    def _format_text(self, result: CrossExamineResult) -> str:
        """文本格式输出"""
        lines = []
        lines.append("=" * 80)
        lines.append("跨审查结果（Cross-examine）")
        lines.append("=" * 80)
        
        # 模型信息
        lines.append(f"模型1（原始）: {result.models_used[0] if result.models_used else '未知'}")
        lines.append(f"模型2（审查）: {result.models_used[1] if len(result.models_used) > 1 else '未知'}")
        
        if result.single_provider:
            lines.append(f"⚠️  {result.provider_warning}")
        
        lines.append("")
        
        # 信任等级
        trust_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        lines.append(f"信任等级: {trust_emoji.get(result.trust_level, '⚪')} {result.trust_level.upper()}")
        lines.append("")
        
        # 可信度统计
        lines.append("--- 可信度分类统计 ---")
        lines.append(f"  ✅ CONFIRMED:     {result.confirmed_count} 对句子")
        lines.append(f"  ⚠️  DISPUTED:      {result.disputed_count} 对句子")
        lines.append(f"  🔍 BLIND_SPOT:    {result.blind_spot_count} 对句子")
        lines.append(f"  ❌ HALLUCINATION: {result.hallucination_count} 对句子")
        lines.append("")
        
        # 总体结论
        if result.agreement and not result.divergences:
            lines.append("✅ 两个模型在此问题上结论一致。")
        else:
            lines.append(f"⚠️  发现 {len(result.divergences)} 处分歧")
        
        lines.append("")
        
        # 分歧详情
        if result.divergences:
            lines.append("分歧点详情：")
            lines.append("-" * 40)
            
            for i, d in enumerate(result.divergences, 1):
                trust_tag = d.get("trust_tag", "DISPUTED")
                lines.append(f"{i}. [{trust_tag}] {d.get('tag', '')}")
                lines.append(f"   模型1: {d['original_sentence']}")
                lines.append(f"   模型2: {d['second_sentence']}")
                lines.append(f"   理由1: {d['reason_model_1']}")
                lines.append(f"   理由2: {d['reason_model_2']}")
                lines.append("")
        
        # 输出摘要
        lines.append("=" * 80)
        lines.append("输出摘要：")
        lines.append(f"原始输出长度: {len(result.original_output)} 字符")
        lines.append(f"第二输出长度: {len(result.second_output)} 字符")
        
        return "\n".join(lines)
    
    def _format_html(self, result: CrossExamineResult) -> str:
        """HTML格式输出（用于报告）"""
        html = []
        html.append('<div class="cross-examine-result">')
        html.append('<h3>跨审查结果（Cross-examine）</h3>')
        
        # 模型信息
        html.append(f'<p><strong>模型1（原始）:</strong> {result.models_used[0] if result.models_used else "未知"}</p>')
        html.append(f'<p><strong>模型2（审查）:</strong> {result.models_used[1] if len(result.models_used) > 1 else "未知"}</p>')
        
        if result.single_provider:
            html.append(f'<p class="warning">⚠️ {result.provider_warning}</p>')
        
        # 信任等级
        trust_level_class = f"trust-{result.trust_level}"
        html.append(f'<p class="trust-level {trust_level_class}">信任等级: {result.trust_level.upper()}</p>')
        
        # 可信度统计
        html.append('<div class="trust-stats">')
        html.append('<h4>可信度分类统计</h4>')
        html.append('<table class="trust-table">')
        html.append(f'<tr><td>✅ CONFIRMED</td><td>{result.confirmed_count} 对句子</td></tr>')
        html.append(f'<tr><td>⚠️ DISPUTED</td><td>{result.disputed_count} 对句子</td></tr>')
        html.append(f'<tr><td>🔍 BLIND_SPOT</td><td>{result.blind_spot_count} 对句子</td></tr>')
        html.append(f'<tr><td>❌ HALLUCINATION</td><td>{result.hallucination_count} 对句子</td></tr>')
        html.append('</table>')
        html.append('</div>')
        
        # 总体结论
        if result.agreement and not result.divergences:
            html.append('<p class="agreement">✅ 两个模型在此问题上结论一致。</p>')
        else:
            html.append(f'<p class="disagreement">⚠️ 发现 {len(result.divergences)} 处分歧</p>')
        
        # 分歧详情
        if result.divergences:
            html.append('<div class="divergences">')
            html.append('<h4>分歧点详情：</h4>')
            
            trust_class_map = {
                "CONFIRMED": "trust-confirmed",
                "DISPUTED": "trust-disputed",
                "BLIND_SPOT": "trust-blindspot",
                "HALLUCINATION": "trust-hallucination",
            }
            
            for i, d in enumerate(result.divergences, 1):
                trust_tag = d.get("trust_tag", "DISPUTED")
                trust_cls = trust_class_map.get(trust_tag, "trust-disputed")
                content_tag = d.get("tag", "")
                
                tag_class = {
                    "[方案分歧]": "divergence-solution",
                    "[事实分歧]": "divergence-fact",
                    "[范围分歧]": "divergence-scope",
                    "[无实质差异]": "divergence-none",
                }.get(content_tag, "divergence-other")
                
                html.append(f'<div class="divergence-item {tag_class} {trust_cls}">')
                html.append(f'<h5>{i}. [{trust_tag}] {content_tag}</h5>')
                html.append(f'<p><strong>模型1:</strong> {d["original_sentence"]}</p>')
                html.append(f'<p><strong>模型2:</strong> {d["second_sentence"]}</p>')
                html.append(f'<p><em>理由1:</em> {d["reason_model_1"]}</p>')
                html.append(f'<p><em>理由2:</em> {d["reason_model_2"]}</p>')
                html.append('</div>')
            
            html.append('</div>')
        
        html.append('</div>')
        return "\n".join(html)


async def cross_examine_file(
    output_file: str,
    requirement_file: Optional[str] = None,
    models: Optional[List[str]] = None,
    allow_single_provider: bool = False,
    line_range: Optional[Tuple[int, int]] = None,
    format_type: str = "text",
) -> str:
    """
    从文件执行跨审查
    
    Args:
        output_file: AI 输出文件路径
        requirement_file: 需求文件路径（可选）
        models: 指定模型列表
        allow_single_provider: 是否允许同 provider
        line_range: 行范围 (start, end)
        format_type: 输出格式
        
    Returns:
        格式化结果
    """
    # 读取文件
    output_path = Path(output_file)
    if not output_path.exists():
        raise FileNotFoundError(f"输出文件不存在: {output_file}")
    
    output_text = output_path.read_text(encoding="utf-8")
    
    # 读取需求
    requirement = ""
    if requirement_file:
        req_path = Path(requirement_file)
        if req_path.exists():
            requirement = req_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"需求文件不存在: {requirement_file}")
    else:
        # 尝试从文件名或元数据推断
        requirement = f"审查文件: {output_file}"
    
    # 检查 API Key 配置 — 必须至少有一个非 local/custom 的 provider 配置了 API Key
    import os
    available_providers = ArsenalClient.get_available_providers()
    # get_available_providers 返回的是无需 API Key 的 provider（如 local/custom）
    # 检查是否有真正配置了 API Key 的 provider
    real_providers = [p for p in available_providers if p not in ("local", "custom")]
    if not real_providers:
        return (
            "错误：需要配置至少一个 provider 的 API Key 才能使用跨审查功能。\n\n"
            "跨审查 (cross-examine) 需要用不同的 AI 模型重新回答同一需求并进行差异分析，\n"
            "这需要调用外部 LLM API。\n\n"
            "请配置以下任一环境变量：\n"
            "  - OPENAI_API_KEY（OpenAI）\n"
            "  - ANTHROPIC_API_KEY（Anthropic）\n"
            "  - DASHSCOPE_API_KEY（通义千问）\n"
            "  - ZHIPU_API_KEY（智谱）\n"
            "  - MOONSHOT_API_KEY（月之暗面）\n"
            "  - DEEPSEEK_API_KEY（DeepSeek）"
        )
    
    # 执行跨审查
    engine = CrossExamineEngine(
        models=models,
        allow_single_provider=allow_single_provider,
    )
    
    result = await engine.run(
        output_text=output_text,
        requirement=requirement,
        line_range=line_range,
    )
    
    # 格式化输出
    return engine.format_result(result, format_type)


def _parse_line_range(range_str: str) -> Tuple[int, int]:
    """解析行范围字符串，如 '10-20'"""
    try:
        start, end = map(int, range_str.split("-"))
        return start, end
    except:
        raise ValueError(f"无效的行范围格式: {range_str}，应为 'start-end'")


async def main():
    """CLI入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="跨审查武器：用不同模型重新回答同一需求，分析差异"
    )
    parser.add_argument(
        "output_file",
        help="AI 输出文件路径（如 output.txt）"
    )
    parser.add_argument(
        "--requirement", "-r",
        help="需求文件路径（可选）"
    )
    parser.add_argument(
        "--models", "-m",
        nargs=2,
        help="指定两个模型（如 gpt-4o-mini claude-3-haiku）"
    )
    parser.add_argument(
        "--single-provider",
        action="store_true",
        help="允许使用同一 provider 的不同模型"
    )
    parser.add_argument(
        "--line-range",
        help="仅审查指定行范围，如 '10-20'"
    )
    parser.add_argument(
        "--format",
        choices=["text", "html", "json"],
        default="text",
        help="输出格式"
    )
    
    args = parser.parse_args()
    
    # 解析行范围
    line_range = None
    if args.line_range:
        line_range = _parse_line_range(args.line_range)
    
    try:
        result = await cross_examine_file(
            output_file=args.output_file,
            requirement_file=args.requirement,
            models=args.models,
            allow_single_provider=args.single_provider,
            line_range=line_range,
            format_type=args.format,
        )
        print(result)
    except Exception as e:
        logger.error(f"跨审查失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())