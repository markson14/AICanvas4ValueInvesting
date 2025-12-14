import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config.history_schema import normalize_history_data
from utils.llm_json import parse_llm_json, get_json_format_instructions


class AIEngine:
    def __init__(self):
        self.prompts_dir = Path(__file__).parent / "prompts"

    def _load_prompt(self, filename: str) -> str:
        with open(self.prompts_dir / filename, "r", encoding="utf-8") as f:
            return f.read()

    def _clean_json(self, content: str) -> str:
        """Helper to clean markdown code blocks from JSON string"""
        content = content.strip()
        # Remove ```json and ``` wrapper
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
        return content.strip()

    async def analyze(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        ticker: str,
        price: float,
        custom_metrics: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        template = self._load_prompt("analyze.txt")
        format_instructions = get_json_format_instructions()

        # Format custom metrics for prompt
        metrics_str = "无"
        if custom_metrics:
            metrics_str = json.dumps(custom_metrics, ensure_ascii=False)

        # Initialize LLM
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
        )

        messages = [
            SystemMessage(
                content=template.format(
                    ticker=ticker, price=price, custom_metrics=metrics_str
                )
                + "\n\n"
                + format_instructions
            ),
            HumanMessage(content=f"分析目标: {ticker}. 当前股价: {price}"),
        ]

        response = await llm.ainvoke(messages)
        result = parse_llm_json(response.content)
        return normalize_history_data(result, ticker=ticker)

    async def react_earnings(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        context: Dict[str, Any],
        financial_snapshot: Dict[str, Any],
        north_star_metrics: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Two-step ReAct process:
        Step 1: Qualitative analysis with react_earnings.txt
        Step 2: Quantitative valuation with react_valuation.txt
        Returns: Complete merged analysis object (same structure as analyze)
        """
        format_instructions = get_json_format_instructions()
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
        )

        # === STEP 1: Qualitative Analysis ===
        template_qual = self._load_prompt("react_earnings.txt")

        # 固定 schema：确保 ticker 等字段可继承
        base_ctx = normalize_history_data(
            context, ticker=(context or {}).get("ticker", "")
        )

        company_name = base_ctx.get("company_name", "Unknown") or "Unknown"
        currency = base_ctx.get("currency", "CNY") or "CNY"
        old_radar = base_ctx.get("radar_scores", {}) or {}
        old_val_type = base_ctx.get("valuation_type", "N/A") or "N/A"

        # Prepare financial string
        metrics = financial_snapshot.get("metrics", {})
        other_metrics = ", ".join(
            [
                f"{k}:{v}"
                for k, v in metrics.items()
                if k
                not in [
                    "revenue",
                    "net_profit",
                    "revenue_growth_yoy",
                    "profit_growth_yoy",
                ]
            ]
        )

        # Format north star metrics
        ns_metrics_str = "无用户定义指标"
        if north_star_metrics:
            ns_metrics_str = json.dumps(north_star_metrics, ensure_ascii=False)

        formatted_qual_prompt = template_qual.format(
            company_name=company_name,
            old_moat_score=old_radar.get("moat", 5),
            old_valuation_verdict=old_val_type,
            old_essence=(base_ctx.get("analysis_normal", {}) or {}).get(
                "essence", "N/A"
            ),
            period=financial_snapshot.get("period", "Unknown"),
            revenue=metrics.get("revenue", "N/A"),
            revenue_growth=metrics.get("revenue_growth_yoy", "N/A"),
            profit=metrics.get("net_profit", "N/A"),
            profit_growth=metrics.get("profit_growth_yoy", "N/A"),
            other_metrics=other_metrics,
            north_star_metrics=ns_metrics_str,
        )

        messages_qual = [
            SystemMessage(content=formatted_qual_prompt + "\n\n" + format_instructions),
            HumanMessage(content="财报已更新，请开始 ReAct 推演。"),
        ]

        response_qual = await llm.ainvoke(messages_qual)
        result_qual = parse_llm_json(response_qual.content)

        # === STEP 2: Quantitative Valuation ===
        template_val = self._load_prompt("react_valuation.txt")

        formatted_val_prompt = template_val.format(
            company_name=company_name,
            react_summary=result_qual.get("react_summary", ""),
            north_star_analysis=result_qual.get("north_star_analysis", ""),
            new_radar_scores=json.dumps(result_qual.get("new_radar_scores", {})),
            revenue=metrics.get("revenue", "N/A"),
            net_profit=metrics.get("net_profit", "N/A"),
            pe_ttm=metrics.get("pe_ttm", "N/A"),
            growth_rate=metrics.get("revenue_growth_yoy", "N/A"),
        )

        messages_val = [
            SystemMessage(content=formatted_val_prompt + "\n\n" + format_instructions),
            HumanMessage(content="请基于以上分析结果进行定量估值。"),
        ]

        response_val = await llm.ainvoke(messages_val)
        result_val = parse_llm_json(response_val.content)

        # === MERGE INTO FIXED JSONL SCHEMA ===
        merged = dict(base_ctx)
        merged.update(
            {
                "company_name": company_name,
                "currency": currency,
                "radar_scores": result_qual.get("new_radar_scores", old_radar),
                "analysis_normal": result_qual.get(
                    "new_analysis_normal", base_ctx.get("analysis_normal", {})
                ),
                "master_views": result_qual.get(
                    "master_views", base_ctx.get("master_views", {})
                ),
                "valuation_type": result_val.get(
                    "valuation_type", base_ctx.get("valuation_type", "")
                ),
                "valuation_params": result_val.get(
                    "valuation_params", base_ctx.get("valuation_params", {})
                ),
                "valuation_explanation": result_val.get(
                    "valuation_explanation", base_ctx.get("valuation_explanation", {})
                ),
                "react_summary": result_qual.get("react_summary", ""),
                "north_star_analysis": result_qual.get("north_star_analysis", ""),
                "valuation_adjustment_reasoning": result_qual.get(
                    "valuation_adjustment_reasoning", ""
                ),
                "fair_value_range": result_val.get("fair_value_range", {}),
                "valuation_verdict": result_val.get("valuation_verdict", "HOLD"),
                "margin_of_safety": result_val.get("margin_of_safety", ""),
                "verdict_reasoning": result_val.get("verdict_reasoning", ""),
                "north_star_metrics": north_star_metrics
                or base_ctx.get("north_star_metrics", []),
                "financial_snapshot": {
                    "revenue": metrics.get("revenue", ""),
                    "net_profit": metrics.get("net_profit", ""),
                    "pe_ttm": metrics.get("pe_ttm", ""),
                    "revenue_growth_yoy": metrics.get("revenue_growth_yoy", ""),
                },
                "reasoning_trace": base_ctx.get("reasoning_trace", ""),
            }
        )

        # 最终再做一次 schema 固定化（补齐缺省 key）
        return normalize_history_data(merged, ticker=merged.get("ticker", ""))
