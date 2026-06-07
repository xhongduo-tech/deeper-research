"""
Sentiment Agent — multi-dimensional public opinion and sentiment analysis.

Performs entity-level and aspect-level sentiment analysis across research
findings, generates opinion profiles, detects risk signals, and produces
comprehensive sentiment narratives for reports.
"""
import logging
from typing import Optional

from app.models.research import SubTask, ResearchFinding
from app.services.sentiment_service import analyze_text_sentiment
from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)


class SentimentAgent:
    """
    Comprehensive sentiment and public opinion analysis agent.

    Capabilities:
    - Document-level and entity-level sentiment scoring
    - Aspect-based opinion extraction (finance, risk, product, market, policy)
    - Temporal trend detection across multiple documents
    - Risk signal identification
    - Multi-source opinion synthesis
    """

    AGENT_TYPE = "sentiment_agent"

    async def analyze(
        self,
        text: str,
        topic: str = "",
        entities: Optional[list[str]] = None,
        domain: str = "general",
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Run full sentiment analysis on a text."""
        if on_progress:
            await on_progress("sentiment_agent", "执行多维情感分析...", 20)

        result = await analyze_text_sentiment(
            text, entities=entities, doc_ref=topic, domain=domain
        )

        if on_progress:
            await on_progress("sentiment_agent", "生成情感洞察报告...", 70)

        narrative = await self._generate_narrative(topic, result, domain)
        result["narrative"] = narrative

        if on_progress:
            await on_progress("sentiment_agent", "舆情分析完成", 100)

        return result

    async def analyze_multi_source(
        self,
        texts: list[dict],  # [{text, source, date}]
        topic: str,
        entities: Optional[list[str]] = None,
        domain: str = "general",
        on_progress: Optional[callable] = None,
    ) -> dict:
        """
        Analyze sentiment across multiple source texts and synthesize findings.
        texts: list of {"text": str, "source": str, "date": str}
        """
        if on_progress:
            await on_progress("sentiment_agent", f"分析{len(texts)}份文本舆情...", 10)

        analyses = []
        for i, item in enumerate(texts[:10]):  # limit to 10 sources
            res = await analyze_text_sentiment(
                item.get("text", ""),
                entities=entities,
                doc_ref=item.get("source", ""),
                domain=domain,
            )
            res["source"] = item.get("source", f"来源{i+1}")
            res["date"] = item.get("date", "")
            analyses.append(res)
            if on_progress:
                pct = 10 + int(70 * (i + 1) / max(len(texts), 1))
                await on_progress("sentiment_agent", f"已分析 {i+1}/{len(texts)} 份文本", pct)

        if on_progress:
            await on_progress("sentiment_agent", "综合多源舆情...", 85)

        synthesis = await self._synthesize_multi_source(topic, analyses, domain)

        if on_progress:
            await on_progress("sentiment_agent", "多源舆情分析完成", 100)

        return {
            "topic": topic,
            "source_count": len(analyses),
            "individual_analyses": analyses,
            "synthesis": synthesis,
        }

    async def detect_risk_signals(
        self,
        text: str,
        topic: str = "",
        domain: str = "general",
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Focused risk signal detection from text."""
        if on_progress:
            await on_progress("sentiment_agent", "扫描风险信号...", 30)

        messages = [
            {
                "role": "system",
                "content": "你是风险预警专家。从文本中识别潜在风险信号，区分短期与长期风险，评估影响程度。",
            },
            {
                "role": "user",
                "content": f"""对以下文本进行风险信号扫描。主题：{topic}，领域：{domain}。

文本：
{text[:2000]}

返回风险分析报告（Markdown格式）：

### 🔴 高风险信号
（直接且紧迫的风险，需立即关注）

### 🟡 中风险信号
（潜在但可管控的风险）

### 🟢 低风险/机会信号
（积极信号或可转化为机会的风险）

### 整体风险评级
评级（高/中/低）及核心理由（1-2句）

### 关键监测指标
需要持续跟踪的3-5个早期预警指标""",
            },
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
        risk_report = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                                 temperature=0.2, max_tokens=1200)

        if on_progress:
            await on_progress("sentiment_agent", "风险信号扫描完成", 100)

        return {"topic": topic, "risk_report": risk_report, "domain": domain}

    async def _generate_narrative(self, topic: str, analysis: dict, domain: str) -> str:
        doc_s = analysis.get("document_sentiment", {})
        entity_list = [
            f"{e['entity']}({e.get('sentiment','neutral')})"
            for e in analysis.get("entity_sentiments", [])[:5]
        ]
        risks = analysis.get("risk_signals", [])
        opps = analysis.get("opportunity_signals", [])

        messages = [
            {
                "role": "system",
                "content": "你是资深舆情分析师，根据情感分析结果撰写专业的舆情摘要报告。",
            },
            {
                "role": "user",
                "content": f"""撰写关于"{topic}"的舆情分析摘要（150-250字）。

整体情感：{doc_s.get('sentiment','neutral')}（极性：{doc_s.get('polarity', 0.0):.2f}）
主要情绪标签：{', '.join(analysis.get('emotion_tags', []))}
关键实体情感：{', '.join(entity_list) or '无'}
风险信号：{'; '.join(risks[:3]) or '无'}
机会信号：{'; '.join(opps[:3]) or '无'}

要求：客观中性，有数据支撑，点明核心观点和主要分歧，给出专业判断。""",
            },
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
        return await chat(messages, model=model, base_url=base_url, api_key=api_key,
                          temperature=0.3, max_tokens=400)

    async def _synthesize_multi_source(self, topic: str, analyses: list[dict], domain: str) -> dict:
        """Synthesize findings across multiple source analyses."""
        all_polarities = [
            a.get("document_sentiment", {}).get("polarity", 0.0) for a in analyses
        ]
        avg_polarity = sum(all_polarities) / len(all_polarities) if all_polarities else 0.0

        all_risks = list(set(
            r for a in analyses for r in a.get("risk_signals", [])
        ))
        all_opps = list(set(
            o for a in analyses for o in a.get("opportunity_signals", [])
        ))
        all_emotions = list(set(
            e for a in analyses for e in a.get("emotion_tags", [])
        ))

        sentiment_dist = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        for a in analyses:
            s = a.get("document_sentiment", {}).get("sentiment", "neutral")
            sentiment_dist[s] = sentiment_dist.get(s, 0) + 1

        # Generate synthesis narrative
        source_summaries = "\n".join(
            f"- [{a.get('source','')}] {a.get('document_sentiment',{}).get('summary','')}"
            for a in analyses[:6]
        )
        messages = [
            {
                "role": "system",
                "content": "你是首席舆情分析师，综合多源信息生成权威舆情报告。",
            },
            {
                "role": "user",
                "content": f"""综合{len(analyses)}份来源分析关于"{topic}"的舆情。

各来源情感摘要：
{source_summaries}

整体极性均值：{avg_polarity:.2f}
情感分布：正面{sentiment_dist['positive']} 负面{sentiment_dist['negative']} 中性{sentiment_dist['neutral']}
共同情绪标签：{', '.join(all_emotions[:6]) or '无'}
主要风险信号：{'; '.join(all_risks[:5]) or '无'}
主要机会信号：{'; '.join(all_opps[:5]) or '无'}

请生成综合舆情报告（200-300字），包括：整体舆情判断、主要分歧点、关键风险、战略建议。""",
            },
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
        narrative = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.3, max_tokens=600)

        return {
            "avg_polarity": round(avg_polarity, 3),
            "sentiment_distribution": sentiment_dist,
            "common_emotions": all_emotions[:8],
            "aggregated_risks": all_risks[:8],
            "aggregated_opportunities": all_opps[:8],
            "narrative": narrative,
        }

    async def run_for_subtask(self, task: SubTask) -> ResearchFinding:
        """Adapter to run as part of the multi-agent pipeline."""
        result = await self.analyze(
            text=task.query,
            topic=task.query,
            domain="general",
        )
        doc_s = result.get("document_sentiment", {})
        sentiment = doc_s.get("sentiment", "neutral")
        polarity = doc_s.get("polarity", 0.0)

        content = f"""## 舆情情感分析：{task.query}

**整体情感**：{sentiment}（极性：{polarity:+.2f}）
**主要情绪**：{', '.join(result.get('emotion_tags', [])[:5]) or '无'}

{result.get('narrative', '')}

**风险信号**：{'; '.join(result.get('risk_signals', [])[:3]) or '无'}
**机会信号**：{'; '.join(result.get('opportunity_signals', [])[:3]) or '无'}"""

        return ResearchFinding(
            sub_task_id=task.id,
            content=content,
            source_type="sentiment_analysis",
            confidence=doc_s.get("confidence", 0.75),
            key_data=[
                f"sentiment: {sentiment}",
                f"polarity: {polarity:+.2f}",
                f"emotions: {', '.join(result.get('emotion_tags', [])[:3])}",
            ],
        )
