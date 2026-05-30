"""
ArsenalClient — 验证武器库统一 LLM 客户端封装

支持 OpenAI / Anthropic / DeepSeek 三种 provider。
复用现有 models.yaml 配置，提供跨审查和溯源追溯的 LLM 调用方法。
"""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import yaml
from loguru import logger

# 复用现有 LLMClient
from .llm_client import LLMClient


@dataclass
class CrossExamineResult:
    """跨审查结果"""
    original_output: str
    second_output: str
    divergences: List[Dict[str, Any]] = field(default_factory=list)
    agreement: bool = True
    single_provider: bool = False
    provider_warning: str = ""
    models_used: List[str] = field(default_factory=list)
    trust_level: str = "green"  # green / yellow / red
    confirmed_count: int = 0
    disputed_count: int = 0
    blind_spot_count: int = 0
    hallucination_count: int = 0


@dataclass
class TraceResult:
    """溯源追踪结果"""
    claims: List[Dict[str, Any]] = field(default_factory=list)
    match_count: int = 0
    total_claims: int = 0
    match_ratio: float = 0.0
    trace_type: str = ""  # "exact" or "semantic"


# ============================================================
# 模块级工具函数 — 用于 cross-examine 四标签可信度分类
# ============================================================

def _normalize_trust(s: str) -> str:
    """标准化文本：去除空白并转小写"""
    import re
    return re.sub(r'\s+', '', s.lower())


def _sentence_overlap_trust(s: str, ref_sents: List[str]) -> float:
    """计算句子与参考文本的重叠度，判断是否对应同一输入段落。
    
    使用 SequenceMatcher 计算与参考句子集中最佳匹配的相似度。
    """
    from difflib import SequenceMatcher
    if not s or not s.strip():
        return 0.0
    s_norm = _normalize_trust(s)
    max_overlap = 0.0
    for ref in ref_sents:
        ref_norm = _normalize_trust(ref)
        if not ref_norm:
            continue
        score = SequenceMatcher(None, s_norm, ref_norm).ratio()
        if score > max_overlap:
            max_overlap = score
    return max_overlap


def classify_trust(
    s1: str, s2: str, orig_sents, second_sents
) -> Tuple[str, str]:
    """
    输出级可信度四标签分类。

    CONFIRMED    — 双方输出语义一致，无需进一步调查
    DISPUTED     — 双方输出存在实质分歧，需要用户判断
    BLIND_SPOT   — 一方提到另一方完全遗漏的关键信息
    HALLUCINATION — 一方输出包含另一方未确认且无法验证的断言

    Args:
        s1, s2: 待比较的两个句子
        orig_sents: 原始参考句子（str 或 List[str]，当前版本未直接使用）
        second_sents: 第二组参考句子（str 或 List[str]，当前版本未直接使用）

    Returns:
        (trust_tag, reason) — 可信度标签和原因说明
    """
    from difflib import SequenceMatcher
    import re

    # 兼容 str 和 List[str]
    if isinstance(orig_sents, str):
        orig_sents = [orig_sents]
    if isinstance(second_sents, str):
        second_sents = [second_sents]

    n1 = _normalize_trust(s1)
    n2 = _normalize_trust(s2)

    # === 第 1 层：精确一致 ===
    if n1 == n2:
        return ("CONFIRMED", "双方输出语义一致，无需进一步调查")

    sim = SequenceMatcher(None, n1, n2).ratio()

    # 量化断言检测（数字 + 度量单位 = 典型不可验证声称）
    quant_pattern = re.compile(
        r'\d+\.?\d*\s*(?:ms|毫秒|并发|%|分|美元|元|F1\b|MB|GB|TB|qps|rps)'
    )

    # === 第 2 层：高相似度（≥60%）===
    if sim >= 0.60:
        # 双方都包含数字但数值不同 → 实质分歧
        nums1 = re.findall(r'\d+', n1)
        nums2 = re.findall(r'\d+', n2)
        if nums1 and nums2 and nums1 != nums2:
            return ("DISPUTED", "双方输出存在实质分歧，需要用户判断")
        return ("CONFIRMED", "双方输出语义一致，无需进一步调查")

    # === 第 3 层：中等相似度（30%~60%）===
    if sim >= 0.30:
        # 3a. 否定词不对称 → 矛盾 → 实质分歧
        neg_words = ['不', '无', '没', '非', '否']
        has_neg_1 = any(w in n1 for w in neg_words)
        has_neg_2 = any(w in n2 for w in neg_words)
        if has_neg_1 != has_neg_2:
            return ("DISPUTED", "双方输出存在实质分歧，需要用户判断")

        # 3b. 只有一方有量化断言 → 编造数据 → 幻觉
        if bool(quant_pattern.search(s1)) != bool(quant_pattern.search(s2)):
            return ("HALLUCINATION", "输出包含另一方未确认且无法验证的断言")

        # 3c. 语义相似且无矛盾/幻觉信号 → 确认一致
        return ("CONFIRMED", "双方输出语义一致，无需进一步调查")

    # === 第 4 层：低相似度（<30%）— 盲区 vs 幻觉 ===
    # 只有一方有量化断言 → 幻觉
    if bool(quant_pattern.search(s1)) != bool(quant_pattern.search(s2)):
        return ("HALLUCINATION", "输出包含另一方未确认且无法验证的断言")

    return ("BLIND_SPOT", "一方提到另一方完全遗漏的关键信息")


class ArsenalClient:
    """
    验证武器库 LLM 客户端
    
    支持 OpenAI / Anthropic / DeepSeek 三种 provider。
    读取 models.yaml 配置，复用现有 LLMClient 抽象。
    单 provider 降级时返回警告，但允许 --single-provider 使用同 provider 不同模型。
    """

    _CONFIG_CACHE: Dict[str, Any] = {}

    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """加载 models.yaml（带缓存）"""
        if cls._CONFIG_CACHE:
            return cls._CONFIG_CACHE
        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cls._CONFIG_CACHE = yaml.safe_load(f)
            return cls._CONFIG_CACHE
        except Exception as e:
            logger.warning(f"加载 models.yaml 失败: {e}")
            return {}

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取已配置 API key 的 provider 列表（apis.yaml 优先）"""
        # 优先使用 APIPoolManager 交叉校验
        try:
            from .api_pool import APIPoolManager
            mgr = APIPoolManager()
            mgr.load()
            available = mgr.get_available_providers()
            if available:
                return available
        except Exception:
            pass

        # 回退：从环境变量检查
        config = cls._load_config()
        providers = config.get("providers", {})
        available = []
        for name, cfg in providers.items():
            if name in ("local", "custom"):
                available.append(name)
                continue
            api_key_env = cfg.get("api_key", "")
            if api_key_env.startswith("${") and api_key_env.endswith("}"):
                env_var = api_key_env[2:-1]
                if os.getenv(env_var):
                    available.append(name)
            elif api_key_env:
                available.append(name)
        return available

    @classmethod
    def get_models_by_provider(cls) -> Dict[str, List[str]]:
        """按 provider 分组返回可用模型"""
        config = cls._load_config()
        models = config.get("models", {})
        grouped: Dict[str, List[str]] = {}
        for model, cfg in models.items():
            provider = cfg.get("provider", "openai")
            grouped.setdefault(provider, []).append(model)
        return grouped

    @classmethod
    def pick_second_model(
        cls, 
        original_model: str, 
        allow_single_provider: bool = False
    ) -> Optional[str]:
        """
        选择与原始模型不同的模型作为第二审查。
        
        Args:
            original_model: 原始生成时使用的模型
            allow_single_provider: 是否允许同 provider 不同模型
            
        Returns:
            选定的 second model，如果无法找到则返回 None
        """
        config = cls._load_config()
        models = config.get("models", {})
        original_cfg = models.get(original_model, {})
        original_provider = original_cfg.get("provider", "openai")
        
        available_providers = cls.get_available_providers()
        grouped = cls.get_models_by_provider()
        
        # 优先：不同 provider
        for provider in available_providers:
            if provider == original_provider:
                continue
            provider_models = grouped.get(provider, [])
            if provider_models:
                return provider_models[0]
        
        # 降级：同 provider 不同模型
        if allow_single_provider:
            provider_models = grouped.get(original_provider, [])
            for model in provider_models:
                if model != original_model:
                    return model
        
        return None

    def __init__(
        self, 
        model: Optional[str] = None, 
        models: Optional[List[str]] = None,
        allow_single_provider: bool = False
    ):
        """
        初始化 ArsenalClient
        
        Args:
            model: 单模型模式
            models: 双模型列表（用于 cross-examine）
            allow_single_provider: 是否允许同 provider
        """
        self.allow_single_provider = allow_single_provider
        self.single_provider = False
        self._config = self._load_config()
        
        if model:
            self.primary = LLMClient(model)
            self.secondary = None
            self._models = [model]
        elif models and len(models) >= 2:
            self.primary = LLMClient(models[0])
            self.secondary = LLMClient(models[1])
            self._models = list(models)
            self._check_single_provider(models[0], models[1])
        else:
            raise ValueError("必须提供 model 或 models（双模型列表）")

    def _check_single_provider(self, model_a: str, model_b: str):
        """检查是否使用了同一 provider"""
        models = self._config.get("models", {})
        provider_a = models.get(model_a, {}).get("provider", "openai")
        provider_b = models.get(model_b, {}).get("provider", "openai")
        self.single_provider = (provider_a == provider_b)
        if self.single_provider and not self.allow_single_provider:
            logger.warning(
                f"两个模型({model_a}, {model_b})使用同一 provider({provider_a})，"
                "非跨模型家族对比。使用 --single-provider 以允许。"
            )

    async def cross_examine(
        self,
        requirement: str,
        output: str,
        line_range: Optional[Tuple[int, int]] = None,
    ) -> CrossExamineResult:
        """
        双模型交叉审查
        
        并行调用两个模型重新回答同一需求，然后进行句子级差异分析。
        
        Args:
            requirement: 原始需求
            output: 原始 AI 输出（作为模型1的参照基线）
            line_range: 可选，仅审查指定行范围
            
        Returns:
            CrossExamineResult 包含差异分析
        """
        if not self.secondary:
            # 单模型模式：尝试自动选择 second model
            second_model = self.pick_second_model(
                self._models[0], self.allow_single_provider
            )
            if second_model:
                self.secondary = LLMClient(second_model)
                self._models.append(second_model)
                self._check_single_provider(self._models[0], second_model)
            else:
                raise RuntimeError(
                    "无法找到可用的第二审查模型。请配置至少两个 provider 的 API key，"
                    "或使用 --single-provider 选项。"
                )
        
        # 并行调用两个模型
        prompt = f"请根据以下需求生成回答：\n\n需求：{requirement}"
        
        # 使用 asyncio.gather 并行调用两个模型
        results = await asyncio.gather(
            self.primary.generate(prompt=prompt, temperature=0.3),
            self.secondary.generate(prompt=prompt, temperature=0.3),
            return_exceptions=True,
        )
        
        # 处理模型1结果
        if isinstance(results[0], Exception):
            logger.warning(f"模型1 ({self._models[0]}) 调用失败，使用文件原始内容: {results[0]}")
            primary_text = output
        else:
            primary_text = results[0].get("content", "")
        
        # 处理模型2结果
        if isinstance(results[1], Exception):
            raise RuntimeError(
                f"模型2 ({self._models[1]}) 调用失败: {results[1]}"
            )
        second_text = results[1].get("content", "")
        
        # 差异分析（纯本地计算，无 LLM 调用）
        divergences = self._analyze_divergences(primary_text, second_text, requirement)
        
        # CONFIRMED 句子仍然作为确认项输出
        confirmed_pair_count = getattr(self, "_cross_examine_confirmed", 0)
        trust_level = getattr(self, "_cross_examine_trust_level", "green")
        disputed_count = getattr(self, "_cross_examine_disputed", 0)
        blind_spot_count = getattr(self, "_cross_examine_blind_spot", 0)
        hallucination_count = getattr(self, "_cross_examine_hallucination", 0)
        
        result = CrossExamineResult(
            original_output=primary_text,
            second_output=second_text,
            divergences=divergences,
            agreement=(len(divergences) == 0),
            single_provider=self.single_provider,
            provider_warning=(
                "同管线第二意见，非跨模型家族对比。"
                if self.single_provider else ""
            ),
            models_used=self._models,
            trust_level=trust_level,
            confirmed_count=confirmed_pair_count,
            disputed_count=disputed_count,
            blind_spot_count=blind_spot_count,
            hallucination_count=hallucination_count,
        )
        return result

    def _analyze_divergences(
        self,
        orig: str,
        second: str,
        requirement: str,
    ) -> List[Dict[str, Any]]:
        """
        句子级差异分析
        
        将两段文本按句子拆分，逐句对比。
        
        输出两层分类：
        1. 内容级差异类型（classify_divergence）：[方案分歧][事实分歧][范围分歧][无实质差异]
        2. 输出级可信度标签（classify_trust）：CONFIRMED / DISPUTED / BLIND_SPOT / HALLUCINATION
        """
        import re
        
        def split_sentences(text: str) -> List[str]:
            """按句号、换行段落拆分"""
            sentences = []
            for para in text.split("\n"):
                para = para.strip()
                if not para:
                    continue
                parts = re.split(r'(?<=[。.!！?？])\s*', para)
                for p in parts:
                    p = p.strip()
                    if p:
                        sentences.append(p)
            return sentences
        
        def normalize(s: str) -> str:
            return re.sub(r'\s+', '', s.lower())
        
        def sentence_overlap(s: str, ref_sents: List[str]) -> float:
            """计算句子与参考文本的重叠度，判断是否对应同一输入段落"""
            s_norm = normalize(s)
            if not s_norm:
                return 0.0
            max_overlap = 0.0
            for ref in ref_sents:
                ref_norm = normalize(ref)
                if not ref_norm:
                    continue
                common = sum(1 for c in set(s_norm) & set(ref_norm))
                total = len(set(s_norm) | set(ref_norm))
                if total > 0:
                    overlap = common / total
                    if overlap > max_overlap:
                        max_overlap = overlap
            return max_overlap
        
        def classify_divergence(
            s1: str, s2: str
        ) -> Tuple[str, str, str]:
            """分类内容级差异类型（辅助信息）"""
            if normalize(s1) == normalize(s2):
                return "无实质差异", "", ""
            
            has_fact_keywords = any(w in s1.lower() or w in s2.lower() 
                for w in ["数字", "日期", "版本", "百分比", "金额", "统计"])
            has_scope_keywords = any(w in s1.lower() or w in s2.lower()
                for w in ["包括", "此外", "另外", "还需", "除"])
            has_approach_keywords = any(w in s1.lower() or w in s2.lower()
                for w in ["建议", "方案", "方法", "推荐", "应该"])
            
            if has_fact_keywords:
                return ("事实分歧", 
                       f"模型1陈述了不同的事实数据",
                       f"模型2给出了不一致的事实陈述")
            elif has_scope_keywords:
                return ("范围分歧",
                       f"模型1的回答范围不同",
                       f"模型2覆盖的内容范围不一致")
            elif has_approach_keywords:
                return ("方案分歧",
                       f"模型1提出了不同的方案/建议",
                       f"模型2给出了不同的建议")
            else:
                return ("无实质差异",
                       f"表述方式不同但结论一致",
                       f"表述方式不同但结论一致")
        
        def classify_trust(
            s1: str, s2: str, orig_sents: List[str], second_sents: List[str]
        ) -> str:
            """
            输出级可信度四标签分类。
            
            CONFIRMED    — 双方输出语义一致，无需进一步调查
            DISPUTED     — 双方输出存在实质分歧，需要用户判断
            BLIND_SPOT   — 一方提到另一方完全遗漏的关键信息
            HALLUCINATION — 一方输出包含另一方未确认且无法验证的断言
            """
            n1 = normalize(s1)
            n2 = normalize(s2)
            
            # 基本一致 → CONFIRMED
            if n1 == n2:
                return "CONFIRMED"
            
            # 一方为空，另一方有内容 → BLIND_SPOT
            if (s1 and not s2) or (s2 and not s1):
                return "BLIND_SPOT"
            
            # 检查是否对应同一输入段落
            overlap_s1 = sentence_overlap(s1, second_sents) if s1 else 0.0
            overlap_s2 = sentence_overlap(s2, orig_sents) if s2 else 0.0
            
            # 高重叠度（≥0.7）表示双方都在讨论同一话题但有分歧 → DISPUTED
            if overlap_s1 >= 0.7 and overlap_s2 >= 0.7:
                return "DISPUTED"
            
            # 一方在对方文本中找不到任何对应 → HALLUCINATION 或 BLIND_SPOT
            if overlap_s1 < 0.3 and overlap_s2 < 0.3:
                # 双方都偏离 → 各自独立判断
                if overlap_s1 < 0.15 and overlap_s2 < 0.15:
                    return "HALLUCINATION"
                return "BLIND_SPOT"
            
            # 一方有对应另一方没有 → BLIND_SPOT (遗漏)
            if overlap_s1 < 0.3 or overlap_s2 < 0.3:
                return "BLIND_SPOT"
            
            # 默认：有部分重叠但不是高度一致 → DISPUTED
            return "DISPUTED"
        
        orig_sents = split_sentences(orig)
        second_sents = split_sentences(second)
        
        divergences = []
        confirmed_count = 0
        disputed_count = 0
        blind_spot_count = 0
        hallucination_count = 0
        
        # 逐句对比
        max_len = max(len(orig_sents), len(second_sents))
        
        for i in range(max_len):
            s1 = orig_sents[i] if i < len(orig_sents) else ""
            s2 = second_sents[i] if i < len(second_sents) else ""
            
            # 跳过双方都为空
            if not s1 and not s2:
                continue
            
            # 内容级差异类型（辅助）
            content_tag, r1, r2 = classify_divergence(s1, s2)
            
            # 输出级可信度标签（主标签）
            trust_tag = classify_trust(s1, s2, orig_sents, second_sents)
            
            # 计数
            if trust_tag == "CONFIRMED":
                confirmed_count += 1
            elif trust_tag == "DISPUTED":
                disputed_count += 1
                divergences.append({
                    "sentence_index": i,
                    "original_sentence": s1[:200],
                    "second_sentence": s2[:200],
                    "tag": f"[{content_tag}]",  # 内容级差异类型（辅助）
                    "trust_tag": trust_tag,      # 输出级可信度标签（主）
                    "reason_model_1": r1,
                    "reason_model_2": r2,
                })
            elif trust_tag == "BLIND_SPOT":
                blind_spot_count += 1
                divergences.append({
                    "sentence_index": i,
                    "original_sentence": s1[:200],
                    "second_sentence": s2[:200],
                    "tag": f"[{content_tag}]",
                    "trust_tag": trust_tag,
                    "reason_model_1": r1,
                    "reason_model_2": r2,
                })
            elif trust_tag == "HALLUCINATION":
                hallucination_count += 1
                divergences.append({
                    "sentence_index": i,
                    "original_sentence": s1[:200],
                    "second_sentence": s2[:200],
                    "tag": f"[{content_tag}]",
                    "trust_tag": trust_tag,
                    "reason_model_1": r1,
                    "reason_model_2": r2,
                })
        
        # 计算整体 trust_level
        total = confirmed_count + disputed_count + blind_spot_count + hallucination_count
        if total > 0:
            dispute_ratio = (disputed_count + blind_spot_count + hallucination_count) / total
            if dispute_ratio <= 0.1:
                self._cross_examine_trust_level = "green"
            elif dispute_ratio <= 0.3:
                self._cross_examine_trust_level = "yellow"
            else:
                self._cross_examine_trust_level = "red"
        else:
            self._cross_examine_trust_level = "green"
        
        # 存储计数供 cross_examine 使用
        self._cross_examine_confirmed = confirmed_count
        self._cross_examine_disputed = disputed_count
        self._cross_examine_blind_spot = blind_spot_count
        self._cross_examine_hallucination = hallucination_count
        
        return divergences

    async def trace_claim(
        self,
        output: str,
        claim: str,
    ) -> TraceResult:
        """
        溯源追踪：在 output 中查找 claim 的来源
        
        支持确定引用（直接匹配）和推断引用（语义相近）。
        使用 embedding 余弦相似度匹配，不可用时降级为编辑距离。
        
        Args:
            output: 待检索的完整文本
            claim: 需要追踪的论断
            
        Returns:
            TraceResult 包含引用来源和类型
        """
        import re
        from difflib import SequenceMatcher
        import numpy as np
        
        def split_sentences(text: str) -> List[str]:
            sentences = []
            for para in text.split("\n"):
                para = para.strip()
                if not para:
                    continue
                parts = re.split(r'(?<=[。.!！?？])\s*', para)
                for p in parts:
                    p = p.strip()
                    if p:
                        sentences.append(p)
            return sentences
        
        def text_similarity_fallback(a: str, b: str) -> float:
            """编辑距离兜底"""
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()
        
        def embed_similarity(claim: str, sentences: List[str]) -> list:
            """使用 sentence-transformers 计算余弦相似度"""
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('all-MiniLM-L6-v2')
                claim_emb = model.encode([claim])[0]
                sent_embs = model.encode(sentences)
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
                return similarities
            except (ImportError, Exception):
                return []
        
        all_sents = split_sentences(output)
        match_method = "编辑距离（降级，embedding 模型不可用）"
        
        # 尝试 embedding
        embed_scores = embed_similarity(claim, all_sents)
        
        # 如果没有指定 claim，自动拆分 output 为句子并检测
        claims_to_trace = []
        
        if claim:
            claims_to_trace = [claim]
        else:
            # 自动选择重要句子（声明性句子）
            for s in all_sents:
                if any(w in s.lower() for w in ["是", "必须", "应当", "应该", "可以", "需要", "能", "会"]):
                    claims_to_trace.append(s)
        
        matched = []
        for c in claims_to_trace:
            best_match = None
            best_score = 0.0
            match_type = "无匹配"
            
            if embed_scores:
                match_method = "embedding 余弦相似度"
                # 从 embedding 结果中取 Top 5
                for sent, score in embed_scores[:5]:
                    if score > best_score:
                        best_score = score
                        best_match = sent
            else:
                # 降级为 SequenceMatcher
                for sent in all_sents:
                    score = text_similarity_fallback(c, sent)
                    if score > best_score:
                        best_score = score
                        best_match = sent
            
            if best_score >= 0.85:
                match_type = "确定引用"
            elif best_score >= 0.65:
                match_type = "推断引用"
            
            if match_type == "无匹配":
                suggestion = f"未找到与「{c[:80]}」匹配的句子。最接近的句子：「{best_match[:150] if best_match else ''}」（相似度 {best_score:.3f}），建议重新表述查询。"
            else:
                suggestion = ""
            
            if best_match:
                matched.append({
                    "claim": c[:200],
                    "source": best_match[:300],
                    "match_type": match_type,
                    "similarity": round(best_score, 3),
                    "match_method": match_method,
                    "suggestion": suggestion,
                })
        
        # 统计可靠引用占比
        reliable = sum(
            1 for m in matched
            if m["match_type"] in ("确定引用", "推断引用")
        )
        total = len(matched)
        
        return TraceResult(
            claims=matched,
            match_count=reliable,
            total_claims=total,
            match_ratio=reliable / total if total > 0 else 0.0,
            trace_type="semantic",
        )

    async def generate_with_model(
        self,
        model_name: str,
        prompt: str,
        temperature: float = 0.3,
    ) -> str:
        """使用指定模型生成文本"""
        client = LLMClient(model_name)
        result = await client.generate(prompt=prompt, temperature=temperature)
        return result.get("content", "")

    def get_models_info(self) -> Dict[str, Any]:
        """获取当前使用的模型信息"""
        info = {
            "primary_model": self._models[0] if self._models else None,
            "secondary_model": self._models[1] if len(self._models) > 1 else None,
            "single_provider": self.single_provider,
            "available_providers": self.get_available_providers(),
        }
        return info