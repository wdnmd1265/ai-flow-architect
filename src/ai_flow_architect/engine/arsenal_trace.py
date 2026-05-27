"""
溯源追踪武器（Trace）

输入文本自动拆句，逐句在原始文档中查找引用来源。
区分确定引用（直接匹配）和推断引用（语义相近），
统计可靠引用占比。
"""

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger

# 设置 HuggingFace 镜像（国内加速），避免首次下载模型超时
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 全局模型缓存，避免每次调用都重新加载
_EMBED_MODEL = None
_EMBED_MODEL_LOCK = False


@dataclass
class TraceConfig:
    """溯源追踪配置"""
    similarity_threshold: float = 0.65
    candidate_count: int = 5
    min_sentence_length: int = 5


@dataclass
class TraceResult:
    """溯源追踪结果"""
    claims: List[Dict[str, Any]] = field(default_factory=list)
    match_count: int = 0
    total_claims: int = 0
    match_ratio: float = 0.0
    trace_type: str = ""  # "exact" or "semantic"


class TraceEngine:
    """
    溯源追踪引擎
    
    核心功能：
    1. 输入自动拆句
    2. 引用类型区分：[确定引用] 和 [推断引用]
    3. 可靠引用占比统计
    4. 相似度匹配（余弦相似度 + 编辑距离）
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.65,
        candidate_count: int = 5,
        min_sentence_length: int = 5,
    ):
        self.config = TraceConfig(
            similarity_threshold=similarity_threshold,
            candidate_count=candidate_count,
            min_sentence_length=min_sentence_length,
        )
    
    def split_sentences(self, text: str) -> List[str]:
        """按句号/换行符/段落切分，支持中英文"""
        sentences = []
        
        for para in text.split("\n"):
            para = para.strip()
            if not para:
                continue
            
            # 按句号、问号、感叹号分句
            parts = re.split(r'(?<=[。.!！?？])\s*', para)
            for part in parts:
                part = part.strip()
                if len(part) >= self.config.min_sentence_length:
                    sentences.append(part)
        
        return sentences
    
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """
        计算文本相似度
        
        优先使用 embedding 余弦相似度，
        不可用时降级为 SequenceMatcher（编辑距离）。
        """
        scores = self._embed_similarity(text_a, [text_b])
        if scores:
            return scores[0][1]
        
        # 降级：SequenceMatcher
        from difflib import SequenceMatcher
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        return SequenceMatcher(None, a, b).ratio()
    
    def _embed_similarity(self, claim: str, sentences: list) -> list:
        """
        使用 sentence-transformers 计算余弦相似度。
        
        首次加载模型设置 60s 超时（含下载），超时则降级。
        模型加载后缓存复用，后续调用直接使用。
        无 API Key 或模型不可用时降级为 SequenceMatcher，
        并在结果中标注降级来源。
        
        Returns:
            list of (sentence, similarity_score) sorted descending
        """
        global _EMBED_MODEL, _EMBED_MODEL_LOCK
        
        if not sentences:
            return []
        
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            
            # 首次加载模型（带超时保护）
            if _EMBED_MODEL is None:
                def _load_model():
                    return SentenceTransformer('all-MiniLM-L6-v2')
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_load_model)
                    try:
                        _EMBED_MODEL = future.result(timeout=60)
                        logger.info("Embedding 模型加载成功 (all-MiniLM-L6-v2)")
                    except FutureTimeoutError:
                        logger.warning("Embedding 模型加载超时（60s），降级为编辑距离匹配")
                        return []
            
            model = _EMBED_MODEL
            claim_emb = model.encode([claim])[0]
            sent_embs = model.encode(sentences)
            
            # 计算余弦相似度
            claim_norm = np.linalg.norm(claim_emb)
            if claim_norm == 0:
                return []
            
            similarities = []
            for i, sent_emb in enumerate(sent_embs):
                sent_norm = np.linalg.norm(sent_emb)
                if sent_norm == 0:
                    similarities.append((sentences[i], 0.0))
                else:
                    cos_sim = float(np.dot(claim_emb, sent_emb) / (claim_norm * sent_norm))
                    similarities.append((sentences[i], cos_sim))
            
            similarities.sort(key=lambda x: x[1], reverse=True)
            logger.debug(f"Embedding 相似度计算完成 | 候选数: {len(similarities)}")
            return similarities
            
        except ImportError:
            logger.warning("sentence-transformers 不可用，降级为编辑距离匹配")
            return []
        except Exception as e:
            logger.warning(f"Embedding 模型不可用: {e}，降级为编辑距离匹配")
            return []
    
    def compute_cosine_similarity(self, text_a: str, text_b: str) -> float:
        """
        计算余弦相似度（基于字符级 n-gram）
        
        不使用外部依赖，纯 Python 实现。
        """
        def char_ngrams(s: str, n: int = 3) -> set:
            s = s.lower()
            return set(s[i:i + n] for i in range(len(s) - n + 1))
        
        a_ngrams = char_ngrams(text_a)
        b_ngrams = char_ngrams(text_b)
        
        if not a_ngrams or not b_ngrams:
            return 0.0
        
        intersection = a_ngrams & b_ngrams
        union = a_ngrams | b_ngrams
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def classify_match(
        self,
        similarity: float,
    ) -> str:
        """
        分类匹配类型
        
        >= 0.85: 确定引用（直接匹配）
        0.65-0.85: 推断引用（语义相近）
        < 0.65: 无匹配
        """
        if similarity >= 0.85:
            return "确定引用"
        elif similarity >= self.config.similarity_threshold:
            return "推断引用"
        else:
            return "无匹配"
    
    def trace(
        self,
        output_text: str,
        claims: Optional[List[str]] = None,
        source_text: Optional[str] = None,
    ) -> TraceResult:
        """
        执行溯源追踪
        
        Args:
            output_text: 待分析的完整文本
            claims: 需要追踪的论断列表（可选，不提供则自动提取）
            source_text: 原始来源文档（可选）
            
        Returns:
            TraceResult
        """
        # 拆分句子
        output_sentences = self.split_sentences(output_text)
        
        # 如果没有指定claims，自动提取声明性句子
        if claims is None:
            claims = self._extract_claims(output_sentences)
        
        # 使用 source_text 或 output_text 作为引用来源
        reference_sentences = (
            self.split_sentences(source_text) if source_text
            else output_sentences
        )
        
        logger.info(f"开始溯源追踪 | 论断数: {len(claims)} | 引用句数: {len(reference_sentences)}")
        
        # 逐句匹配
        matched_claims = []
        for claim in claims:
            best_match = self._find_best_match(claim, reference_sentences)
            matched_claims.append(best_match)
        
        # 统计可靠引用
        reliable_count = sum(
            1 for m in matched_claims
            if m["match_type"] in ("确定引用", "推断引用")
        )
        total = len(matched_claims)
        
        result = TraceResult(
            claims=matched_claims,
            match_count=reliable_count,
            total_claims=total,
            match_ratio=reliable_count / total if total > 0 else 0.0,
            trace_type="semantic",
        )
        
        logger.info(f"溯源追踪完成 | 可靠引用: {reliable_count}/{total} ({result.match_ratio:.1%})")
        return result
    
    def _extract_claims(self, sentences: List[str]) -> List[str]:
        """自动提取声明性句子"""
        claim_keywords = [
            "是", "必须", "应当", "应该", "可以", "需要", "能", "会",
            "is", "must", "should", "can", "will", "need", "required",
            "定义", "称为", "定义为", "指", "包括", "包含",
        ]
        
        claims = []
        for sent in sentences:
            if any(kw in sent.lower() for kw in claim_keywords):
                claims.append(sent)
        
        # 如果没有找到声明性句子，使用所有句子
        if not claims:
            claims = sentences
        
        return claims
    
    def _find_best_match(
        self,
        claim: str,
        reference_sentences: List[str],
    ) -> Dict[str, Any]:
        """查找最佳匹配句子（优先 embedding，降级编辑距离）"""
        best_score = 0.0
        best_match = ""
        match_method = "编辑距离（降级，embedding 模型不可用）"
        
        # 尝试使用 embedding 相似度
        embedding_scores = self._embed_similarity(claim, reference_sentences)
        
        if embedding_scores:
            # embedding 可用
            match_method = "embedding 余弦相似度"
            # 取 Top 5 候选
            scored = embedding_scores[:self.config.candidate_count]
        else:
            # 降级为 SequenceMatcher
            from difflib import SequenceMatcher
            scored = []
            for ref in reference_sentences:
                if len(ref) < self.config.min_sentence_length:
                    continue
                score = SequenceMatcher(None, claim.lower().strip(), ref.lower().strip()).ratio()
                scored.append((ref, score))
            scored.sort(key=lambda x: x[1], reverse=True)
        
        candidates = scored[:self.config.candidate_count]
        if candidates:
            best_match, best_score = candidates[0]
        
        # 分类
        match_type = self.classify_match(best_score)
        
        # 无匹配时提供最接近句子
        closest_sentences = ""
        suggestion = ""
        if match_type == "无匹配":
            if candidates:
                closest_items = []
                for text, score in candidates[:5]:
                    closest_items.append(f"  [{score:.2f}] {text[:150]}")
                closest_sentences = "\n".join(closest_items)
                if closest_items:
                    suggestion = f"未找到与「{claim[:80]}」匹配的句子。最接近的句子：「{closest_items[0].lstrip()}」，建议重新表述查询。"
            else:
                suggestion = f"未找到与「{claim[:80]}」匹配的句子。建议重新表述查询。"
        
        return {
            "claim": claim,
            "source": best_match if best_match else "无匹配",
            "match_type": match_type,
            "similarity": round(best_score, 3),
            "candidates": [
                {"text": t[:150], "score": round(s, 3)}
                for t, s in candidates[:self.config.candidate_count]
            ],
            "closest_sentences": closest_sentences,
            "suggestion": suggestion,
            "match_method": match_method,
        }
    
    def trace_single_claim(
        self,
        output_text: str,
        claim: str,
        source_text: Optional[str] = None,
    ) -> TraceResult:
        """
        追踪单个论断
        
        Args:
            output_text: 完整文本
            claim: 单个论断
            source_text: 原始来源
            
        Returns:
            TraceResult
        """
        return self.trace(
            output_text=output_text,
            claims=[claim],
            source_text=source_text,
        )
    
    def format_result(
        self,
        result: TraceResult,
        format_type: str = "text",
    ) -> str:
        """格式化溯源结果"""
        if format_type == "json":
            import json
            return json.dumps({
                "claims": result.claims,
                "match_count": result.match_count,
                "total_claims": result.total_claims,
                "match_ratio": result.match_ratio,
                "trace_type": result.trace_type,
            }, ensure_ascii=False, indent=2)
        
        elif format_type == "html":
            return self._format_html(result)
        
        else:  # text
            return self._format_text(result)
    
    def _format_text(self, result: TraceResult) -> str:
        """文本格式输出"""
        lines = []
        lines.append("=" * 80)
        lines.append("溯源追踪结果（Trace）")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"论断总数: {result.total_claims}")
        lines.append(f"可靠引用: {result.match_count} ({result.match_ratio:.1%})")
        lines.append(f"  - 确定引用: {sum(1 for m in result.claims if m['match_type'] == '确定引用')}")
        lines.append(f"  - 推断引用: {sum(1 for m in result.claims if m['match_type'] == '推断引用')}")
        lines.append(f"  - 无匹配:   {sum(1 for m in result.claims if m['match_type'] == '无匹配')}")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        
        for i, claim in enumerate(result.claims, 1):
            lines.append(f"{i}. 论断: {claim['claim']}")
            lines.append(f"   类型: [{claim['match_type']}]")
            lines.append(f"   相似度: {claim['similarity']:.3f}")
            lines.append(f"   匹配方法: {claim.get('match_method', '未知')}")
            lines.append(f"   来源: {claim['source']}")
            
            if claim["match_type"] == "无匹配":
                lines.append(f"   最接近句子:")
                if claim["closest_sentences"]:
                    lines.append(claim["closest_sentences"])
                if claim["suggestion"]:
                    lines.append(f"   {claim['suggestion']}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_html(self, result: TraceResult) -> str:
        """HTML格式输出"""
        html = []
        html.append('<div class="trace-results">')
        html.append('<h3>溯源追踪结果（Trace）</h3>')
        html.append(f'<p><strong>论断总数:</strong> {result.total_claims}</p>')
        html.append(f'<p><strong>可靠引用:</strong> {result.match_count} ({result.match_ratio:.1%})</p>')
        
        html.append('<table class="trace-table">')
        html.append('<thead><tr>')
        html.append('<th>论断</th><th>类型</th><th>相似度</th><th>来源</th>')
        html.append('</tr></thead>')
        html.append('<tbody>')
        
        for claim in result.claims:
            type_class = {
                "确定引用": "match-exact",
                "推断引用": "match-semantic",
                "无匹配": "match-none",
            }.get(claim["match_type"], "")
            
            html.append(f'<tr class="{type_class}">')
            html.append(f'<td>{claim["claim"][:100]}</td>')
            html.append(f'<td>[{claim["match_type"]}]</td>')
            html.append(f'<td>{claim["similarity"]:.3f}</td>')
            html.append(f'<td>{claim["source"][:150]}</td>')
            html.append('</tr>')
        
        html.append('</tbody></table>')
        html.append('</div>')
        return "\n".join(html)


async def trace_file(
    file_path: str,
    claim: Optional[str] = None,
    source_file: Optional[str] = None,
    format_type: str = "text",
) -> str:
    """
    对文件执行溯源追踪
    
    Args:
        file_path: 待追踪的文件路径
        claim: 特定论断（可选）
        source_file: 原始来源文件路径（可选）
        format_type: 输出格式
        
    Returns:
        格式化结果
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    output_text = path.read_text(encoding="utf-8")
    
    source_text = None
    if source_file:
        src_path = Path(source_file)
        if src_path.exists():
            source_text = src_path.read_text(encoding="utf-8")
    
    engine = TraceEngine()
    
    if claim:
        result = engine.trace_single_claim(
            output_text=output_text,
            claim=claim,
            source_text=source_text,
        )
    else:
        result = engine.trace(
            output_text=output_text,
            source_text=source_text,
        )
    
    return engine.format_result(result, format_type)


async def main():
    """CLI入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="溯源追踪武器：在输出文本中追踪论断来源"
    )
    parser.add_argument(
        "file",
        help="待追踪的文件路径"
    )
    parser.add_argument(
        "--claim", "-c",
        help="特定论断（可选，不提供则自动提取所有声明性句子）"
    )
    parser.add_argument(
        "--source", "-s",
        help="原始来源文件路径（可选）"
    )
    parser.add_argument(
        "--format",
        choices=["text", "html", "json"],
        default="text",
        help="输出格式"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.65,
        help="相似度阈值（默认 0.65）"
    )
    
    args = parser.parse_args()
    
    try:
        engine = TraceEngine(similarity_threshold=args.threshold)
        
        path = Path(args.file)
        if not path.exists():
            print(f"文件不存在: {args.file}")
            sys.exit(1)
        
        output_text = path.read_text(encoding="utf-8")
        
        source_text = None
        if args.source:
            src_path = Path(args.source)
            if not src_path.exists():
                print(f"来源文件不存在: {args.source}")
                sys.exit(1)
            source_text = src_path.read_text(encoding="utf-8")
        
        if args.claim:
            result = engine.trace_single_claim(
                output_text=output_text,
                claim=args.claim,
                source_text=source_text,
            )
        else:
            result = engine.trace(
                output_text=output_text,
                source_text=source_text,
            )
        
        output = engine.format_result(result, args.format)
        print(output)
        
    except Exception as e:
        logger.error(f"溯源追踪失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())