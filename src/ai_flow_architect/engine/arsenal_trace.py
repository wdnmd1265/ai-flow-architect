"""
溯源追踪武器（Trace）

V2.2 External Trace 升级：
- V2.1: 句子级拆句 → embedding 匹配 → 确定/推断/无匹配
- V2.2: 短语级提取 → 推理链推断 → 诚实双重标注 → 区分声称依据和验证依据
"""

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

from loguru import logger

# 设置 HuggingFace 镜像（国内加速），避免首次下载模型超时
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 全局模型缓存，避免每次调用都重新加载
_EMBED_MODEL = None


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
    # V2.2 External Trace 新增
    reasoning_chain: Optional["ReasoningChain"] = None
    phrase_claims: List[Dict[str, Any]] = field(default_factory=list)
    inference_model: str = ""  # 标注推断所用模型
    honesty_label: str = ""   # 诚实标注


@dataclass
class ReasoningStep:
    """推理链中的单步"""
    step_id: int
    content: str              # 推理内容
    step_type: str            # "fact" / "inference" / "assumption" / "omission"
    evidence: str             # 支撑依据（声称的或验证的）
    evidence_type: str        # "strong_match" / "claimed" / "none"
    confidence: str           # "high" / "medium" / "low"
    source_phrase: str = ""   # 对应的原文短语


@dataclass
class ReasoningChain:
    """推理链"""
    steps: List[ReasoningStep] = field(default_factory=list)
    source_model: str = ""         # 推断所用模型
    honesty_label: str = ""        # 诚实标注
    total_steps: int = 0
    fact_count: int = 0
    inference_count: int = 0
    assumption_count: int = 0
    omission_count: int = 0
    strong_match_count: int = 0
    claimed_evidence_count: int = 0
    overall_confidence: str = ""   # 整体置信度


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

    # ================================================================
    # V2.2 External Trace 升级
    # ================================================================

    def split_phrases(self, text: str) -> List[Dict[str, Any]]:
        """
        短语级拆分（比句子更细粒度）

        拆分策略：
        1. 先按句子拆
        2. 每个句子按逗号、分号、"并且"、"但是"、"因为"、"所以" 等拆成短语
        3. 每个短语记录：原文、所属句子、位置
        """
        sentences = self.split_sentences(text)
        phrases = []

        # 拆分标记
        split_patterns = r'[,，;；](?!\d)|(?:并且|但是|因为|所以|然而|同时|另外|此外|然后|如果|除非|即使|虽然|尽管|不过|而是|以及|或者)'

        for sent_idx, sentence in enumerate(sentences):
            parts = re.split(split_patterns, sentence)
            for part_idx, part in enumerate(parts):
                part = part.strip()
                if len(part) >= 3:
                    phrases.append({
                        "phrase": part,
                        "sentence": sentence,
                        "sentence_idx": sent_idx,
                        "phrase_idx": part_idx,
                    })

        return phrases

    def trace_reasoning(
        self,
        output_text: str,
        source_text: Optional[str] = None,
        model_name: str = "unknown",
    ) -> TraceResult:
        """
        External Trace — 推理链推断

        流程：
        1. 短语级拆分
        2. 每个短语匹配来源（embedding / 编辑距离）
        3. LLM 反向推断推理路径
        4. 诚实双重标注

        Args:
            output_text: AI 生成的输出文本
            source_text: 原始来源文档（可选）
            model_name: 被审查的 AI 模型名

        Returns:
            TraceResult（含推理链 + 短语级证据）
        """
        logger.info(f"开始 External Trace | 模型: {model_name}")

        # Step 1: 短语级拆分
        phrases = self.split_phrases(output_text)
        logger.info(f"短语拆分完成 | {len(phrases)} 个短语")

        # Step 2: 每个短语匹配来源
        reference_sentences = (
            self.split_sentences(source_text) if source_text
            else self.split_sentences(output_text)
        )

        phrase_claims = []
        for ph in phrases:
            match = self._find_best_match(ph["phrase"], reference_sentences)
            match["sentence_idx"] = ph["sentence_idx"]
            match["sentence"] = ph["sentence"]
            phrase_claims.append(match)

        # Step 3: 构建推理链
        chain = self._build_reasoning_chain(
            output_text=output_text,
            phrase_claims=phrase_claims,
            source_text=source_text,
            model_name=model_name,
        )

        # Step 4: 句子级匹配（兼容旧接口）
        sentences = self.split_sentences(output_text)
        claims = self._extract_claims(sentences)
        matched_claims = []
        for claim in claims:
            best_match = self._find_best_match(claim, reference_sentences)
            matched_claims.append(best_match)

        reliable_count = sum(
            1 for m in matched_claims
            if m["match_type"] in ("确定引用", "推断引用")
        )

        # 诚实标注
        honesty = self._build_honesty_label(model_name, chain, len(matched_claims))

        result = TraceResult(
            claims=matched_claims,
            match_count=reliable_count,
            total_claims=len(matched_claims),
            match_ratio=reliable_count / len(matched_claims) if matched_claims else 0.0,
            trace_type="external_reasoning",
            reasoning_chain=chain,
            phrase_claims=phrase_claims,
            inference_model=model_name,
            honesty_label=honesty,
        )

        logger.info(
            f"External Trace 完成 | 推理步数: {chain.total_steps} | "
            f"事实: {chain.fact_count} | 推断: {chain.inference_count} | "
            f"假设: {chain.assumption_count}"
        )
        return result

    def _build_reasoning_chain(
        self,
        output_text: str,
        phrase_claims: List[Dict[str, Any]],
        source_text: Optional[str],
        model_name: str,
    ) -> "ReasoningChain":
        """
        构建推理链

        基于短语级匹配结果，推断每个论断的推理路径。
        不调用 LLM（纯规则推断），保持零成本。
        """
        steps = []

        for idx, claim in enumerate(phrase_claims):
            phrase = claim["claim"]
            match_type = claim["match_type"]
            similarity = claim["similarity"]

            # 推断推理步类型
            if match_type == "确定引用" and similarity >= 0.9:
                step_type = "fact"
                confidence = "high"
                evidence_type = "strong_match"  # 文本高度匹配，非外部验证
            elif match_type == "确定引用":
                step_type = "fact"
                confidence = "high"
                evidence_type = "claimed"
            elif match_type == "推断引用":
                step_type = "inference"
                confidence = "medium"
                evidence_type = "claimed"
            else:  # 无匹配
                # 检查是否包含推断性关键词
                inference_keywords = ["可能", "也许", "应该", "大概", "或许", "perhaps", "maybe", "likely", "might"]
                if any(kw in phrase.lower() for kw in inference_keywords):
                    step_type = "assumption"
                    confidence = "low"
                else:
                    step_type = "omission"
                    confidence = "low"
                evidence_type = "none"

            steps.append(ReasoningStep(
                step_id=idx + 1,
                content=phrase,
                step_type=step_type,
                evidence=claim.get("source", "无匹配"),
                evidence_type=evidence_type,
                confidence=confidence,
                source_phrase=claim.get("sentence", ""),
            ))

        # 统计
        chain = ReasoningChain(
            steps=steps,
            source_model=model_name,
            total_steps=len(steps),
            fact_count=sum(1 for s in steps if s.step_type == "fact"),
            inference_count=sum(1 for s in steps if s.step_type == "inference"),
            assumption_count=sum(1 for s in steps if s.step_type == "assumption"),
            omission_count=sum(1 for s in steps if s.step_type == "omission"),
            strong_match_count=sum(1 for s in steps if s.evidence_type == "strong_match"),
            claimed_evidence_count=sum(1 for s in steps if s.evidence_type == "claimed"),
        )

        # 整体置信度
        if chain.fact_count >= chain.total_steps * 0.7:
            chain.overall_confidence = "high"
        elif chain.fact_count + chain.inference_count >= chain.total_steps * 0.5:
            chain.overall_confidence = "medium"
        else:
            chain.overall_confidence = "low"

        return chain

    def _build_honesty_label(
        self,
        model_name: str,
        chain: "ReasoningChain",
        claim_count: int,
    ) -> str:
        """
        构建诚实标注

        标注内容：
        - 推断所用模型
        - 推断 vs 确认的比例
        - 明确声明"非原始推理记录"
        """
        parts = []
        parts.append(f"本推理路径由 {model_name} 推断生成，非原始推理记录。")
        parts.append(
            f"共 {chain.total_steps} 步："
            f"事实 {chain.fact_count}、"
            f"推断 {chain.inference_count}、"
            f"假设 {chain.assumption_count}、"
            f"遗漏 {chain.omission_count}。"
        )
        parts.append(
            f"证据类型："
            f"强匹配 {chain.strong_match_count}、"
            f"模型声称 {chain.claimed_evidence_count}、"
            f"无依据 {chain.total_steps - chain.strong_match_count - chain.claimed_evidence_count}。"
        )
        return " ".join(parts)
    
    def format_result(
        self,
        result: TraceResult,
        format_type: str = "text",
    ) -> str:
        """格式化溯源结果"""
        if format_type == "json":
            import json
            data = {
                "claims": result.claims,
                "match_count": result.match_count,
                "total_claims": result.total_claims,
                "match_ratio": result.match_ratio,
                "trace_type": result.trace_type,
                "honesty_label": result.honesty_label,
                "inference_model": result.inference_model,
            }
            if result.reasoning_chain:
                data["reasoning_chain"] = {
                    "total_steps": result.reasoning_chain.total_steps,
                    "fact_count": result.reasoning_chain.fact_count,
                    "inference_count": result.reasoning_chain.inference_count,
                    "assumption_count": result.reasoning_chain.assumption_count,
                    "omission_count": result.reasoning_chain.omission_count,
                    "overall_confidence": result.reasoning_chain.overall_confidence,
                    "steps": [
                        {
                            "step_id": s.step_id,
                            "content": s.content,
                            "type": s.step_type,
                            "evidence": s.evidence,
                            "evidence_type": s.evidence_type,
                            "confidence": s.confidence,
                        }
                        for s in result.reasoning_chain.steps
                    ],
                }
            if result.phrase_claims:
                data["phrase_claims"] = result.phrase_claims
            return json.dumps(data, ensure_ascii=False, indent=2)

        elif format_type == "html":
            return self._format_html(result)

        else:  # text
            return self._format_text(result)
    
    def _format_text(self, result: TraceResult) -> str:
        """文本格式输出"""
        lines = []
        lines.append("=" * 80)

        # 根据 trace_type 选择标题
        if result.trace_type == "external_reasoning":
            lines.append("溯源追踪结果（External Trace V2.2）")
        else:
            lines.append("溯源追踪结果（Trace）")

        lines.append("=" * 80)
        lines.append("")

        # 诚实标注
        if result.honesty_label:
            lines.append(f"⚠ 诚实标注: {result.honesty_label}")
            lines.append("")

        lines.append(f"论断总数: {result.total_claims}")
        lines.append(f"可靠引用: {result.match_count} ({result.match_ratio:.1%})")
        lines.append(f"  - 确定引用: {sum(1 for m in result.claims if m['match_type'] == '确定引用')}")
        lines.append(f"  - 推断引用: {sum(1 for m in result.claims if m['match_type'] == '推断引用')}")
        lines.append(f"  - 无匹配:   {sum(1 for m in result.claims if m['match_type'] == '无匹配')}")

        # 推理链统计
        if result.reasoning_chain:
            chain = result.reasoning_chain
            lines.append("")
            lines.append(f"推理链（由 {chain.source_model} 推断）:")
            lines.append(f"  总步数: {chain.total_steps}")
            lines.append(f"  事实: {chain.fact_count} | 推断: {chain.inference_count} | 假设: {chain.assumption_count} | 遗漏: {chain.omission_count}")
            lines.append(f"  证据类型: 强匹配 {chain.strong_match_count} | 模型声称 {chain.claimed_evidence_count}")
            lines.append(f"  整体置信度: {chain.overall_confidence}")

        lines.append("")
        lines.append("=" * 80)
        lines.append("")

        # 推理链详情
        if result.reasoning_chain and result.reasoning_chain.steps:
            lines.append("--- 推理路径 ---")
            lines.append("")
            type_labels = {
                "fact": "事实",
                "inference": "推断",
                "assumption": "假设",
                "omission": "遗漏",
            }
            conf_colors = {
                "high": "🟢",
                "medium": "🟡",
                "low": "🔴",
            }
            evidence_labels = {
                "strong_match": "强匹配",
                "claimed": "模型声称",
                "none": "无依据",
            }

            for step in result.reasoning_chain.steps:
                conf_icon = conf_colors.get(step.confidence, "⚪")
                type_label = type_labels.get(step.step_type, step.step_type)
                ev_label = evidence_labels.get(step.evidence_type, step.evidence_type)
                lines.append(f"  {step.step_id}. {conf_icon} [{type_label}] {step.content}")
                lines.append(f"     依据: {step.evidence[:80]}" + ("..." if len(step.evidence) > 80 else ""))
                lines.append(f"     证据类型: {ev_label}")
                lines.append("")

            lines.append("⚠ 以上推理路径由模型推断生成，非原始推理记录。")
            lines.append("")

        # 句子级匹配
        lines.append("--- 句子级匹配 ---")
        lines.append("")
        for i, claim in enumerate(result.claims, 1):
            lines.append(f"{i}. 论断: {claim['claim']}")
            lines.append(f"   类型: [{claim['match_type']}]")
            lines.append(f"   相似度: {claim['similarity']:.3f}")
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
        """HTML格式输出（V2.2 交互升级）"""
        html = []
        html.append('<div class="trace-results" style="font-family:-apple-system,sans-serif;max-width:900px;margin:0 auto;color:#c9d1d9;">')

        # 标题
        if result.trace_type == "external_reasoning":
            html.append('<h3 style="color:#58a6ff;">溯源追踪结果（External Trace V2.2）</h3>')
        else:
            html.append('<h3>溯源追踪结果（Trace）</h3>')

        # 诚实标注
        if result.honesty_label:
            html.append(
                f'<div style="background:rgba(210,153,34,0.1);border:1px solid #d29922;'
                f'border-radius:8px;padding:12px 16px;margin:12px 0;font-size:13px;color:#d29922;">'
                f'⚠ {result.honesty_label}'
                f'</div>'
            )

        # 统计行
        html.append(f'<p><strong>论断总数:</strong> {result.total_claims}</p>')
        html.append(f'<p><strong>可靠引用:</strong> {result.match_count} ({result.match_ratio:.1%})</p>')

        # 推理链统计
        if result.reasoning_chain:
            chain = result.reasoning_chain
            conf_color = {"high": "#3fb950", "medium": "#d29922", "low": "#f85149"}.get(chain.overall_confidence, "#8b949e")
            html.append(
                f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                f'padding:16px;margin:16px 0;">'
                f'<div style="display:flex;gap:24px;flex-wrap:wrap;">'
                f'<div><strong style="color:{conf_color};">{chain.fact_count}</strong> <span style="color:#8b949e;">事实</span></div>'
                f'<div><strong style="color:#d29922;">{chain.inference_count}</strong> <span style="color:#8b949e;">推断</span></div>'
                f'<div><strong style="color:#f85149;">{chain.assumption_count}</strong> <span style="color:#8b949e;">假设</span></div>'
                f'<div><strong style="color:#f85149;">{chain.omission_count}</strong> <span style="color:#8b949e;">遗漏</span></div>'
                f'</div>'
                f'<div style="font-size:12px;color:#8b949e;margin-top:8px;">'
                f'证据: 强匹配 {chain.strong_match_count} | 模型声称 {chain.claimed_evidence_count} | '
                f'无依据 {chain.total_steps - chain.strong_match_count - chain.claimed_evidence_count}'
                f'</div>'
                f'<div style="font-size:12px;color:#8b949e;margin-top:4px;">'
                f'推断模型: {chain.source_model} | 整体置信度: '
                f'<span style="color:{conf_color};font-weight:700;">{chain.overall_confidence}</span>'
                f'</div>'
                f'</div>'
            )

        # 推理路径（可折叠）
        if result.reasoning_chain and result.reasoning_chain.steps:
            html.append('<details style="margin:16px 0;">')
            html.append(
                '<summary style="cursor:pointer;padding:10px 16px;background:#161b22;'
                'border:1px solid #30363d;border-radius:6px;font-size:14px;font-weight:600;'
                'color:#58a6ff;">推理路径（点击展开）</summary>'
            )

            type_labels = {"fact": "事实", "inference": "推断", "assumption": "假设", "omission": "遗漏"}
            type_colors = {"fact": "#3fb950", "inference": "#d29922", "assumption": "#f85149", "omission": "#f85149"}
            evidence_labels = {"strong_match": "强匹配", "claimed": "模型声称", "none": "无依据"}

            html.append('<div style="padding:8px;">')
            for step in result.reasoning_chain.steps:
                color = type_colors.get(step.step_type, "#8b949e")
                type_label = type_labels.get(step.step_type, step.step_type)
                ev_label = evidence_labels.get(step.evidence_type, step.evidence_type)
                conf_bar = {"high": "▓▓▓▓▓", "medium": "▓▓▓░░", "low": "▓░░░░"}.get(step.confidence, "░░░░░")

                html.append(
                    f'<div style="border-left:3px solid {color};padding:8px 12px;margin:6px 0;'
                    f'background:rgba(255,255,255,0.02);border-radius:0 4px 4px 0;">'
                    f'<div style="font-size:13px;">'
                    f'<span style="color:{color};font-weight:700;">[{type_label}]</span> '
                    f'{step.content}'
                    f'</div>'
                    f'<div style="font-size:11px;color:#8b949e;margin-top:4px;">'
                    f'依据: {step.evidence[:100]}' + ('...' if len(step.evidence) > 100 else '') + f' '
                    f'| 证据: {ev_label} '
                    f'| 置信度: {conf_bar}'
                    f'</div>'
                    f'</div>'
                )

            html.append('</div>')
            html.append('</details>')

        # 句子级匹配表格
        html.append('<details style="margin:16px 0;" open>')
        html.append(
            '<summary style="cursor:pointer;padding:10px 16px;background:#161b22;'
            'border:1px solid #30363d;border-radius:6px;font-size:14px;font-weight:600;'
            'color:#c9d1d9;">句子级匹配</summary>'
        )

        html.append('<table style="width:100%;border-collapse:collapse;margin:8px 0;">')
        html.append('<thead><tr style="border-bottom:1px solid #30363d;">')
        html.append('<th style="text-align:left;padding:8px;font-size:12px;color:#8b949e;">论断</th>')
        html.append('<th style="text-align:left;padding:8px;font-size:12px;color:#8b949e;">类型</th>')
        html.append('<th style="text-align:left;padding:8px;font-size:12px;color:#8b949e;">相似度</th>')
        html.append('<th style="text-align:left;padding:8px;font-size:12px;color:#8b949e;">来源</th>')
        html.append('</tr></thead><tbody>')

        for claim in result.claims:
            type_class = {
                "确定引用": "color:#3fb950",
                "推断引用": "color:#d29922",
                "无匹配": "color:#f85149",
            }.get(claim["match_type"], "")

            html.append(
                f'<tr style="border-bottom:1px solid #30363d;">'
                f'<td style="padding:8px;font-size:13px;">{claim["claim"][:100]}</td>'
                f'<td style="padding:8px;font-size:13px;{type_class}">[{claim["match_type"]}]</td>'
                f'<td style="padding:8px;font-size:13px;">{claim["similarity"]:.3f}</td>'
                f'<td style="padding:8px;font-size:13px;color:#8b949e;">{claim["source"][:150]}</td>'
                f'</tr>'
            )

        html.append('</tbody></table>')
        html.append('</details>')

        html.append('</div>')
        return "\n".join(html)


async def trace_file(
    file_path: str,
    claim: Optional[str] = None,
    source_file: Optional[str] = None,
    format_type: str = "text",
    trace_type: str = "sentence",
    model_name: str = "unknown",
) -> str:
    """
    对文件执行溯源追踪

    Args:
        file_path: 待追踪的文件路径
        claim: 特定论断（可选）
        source_file: 原始来源文件路径（可选）
        format_type: 输出格式
        trace_type: "sentence"（句子级）或 "external"（推理链推断）
        model_name: 被审查的 AI 模型名

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

    if trace_type == "external":
        # V2.2 External Trace
        result = engine.trace_reasoning(
            output_text=output_text,
            source_text=source_text,
            model_name=model_name,
        )
    elif claim:
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