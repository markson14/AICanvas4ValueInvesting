import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


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
            ),
            HumanMessage(content=f"分析目标: {ticker}. 当前股价: {price}"),
        ]

        response = await llm.ainvoke(messages)
        content = self._clean_json(response.content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Fallback or error handling
            print(f"JSON Parse Error: {e}\nContent: {content}")
            raise ValueError("AI 返回的数据格式不正确，无法解析为 JSON")

    async def challenge(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        context: Dict[str, Any],
        bear_argument: str,
    ) -> Dict[str, Any]:

        template = self._load_prompt("challenge.txt")

        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.8,  # Higher temp for creative critique
        )

        # Extract context
        company_name = context.get("company_name", "Unknown")
        radar = context.get("radar_scores", {})
        original_reasoning = context.get("reasoning_trace", "N/A")

        formatted_system_prompt = template.format(
            company_name=company_name,
            original_moat_score=radar.get("moat", 5),
            original_valuation_score=radar.get("valuation", 5),
            original_reasoning=original_reasoning,
            bear_argument=bear_argument,
        )

        messages = [
            SystemMessage(content=formatted_system_prompt),
            HumanMessage(content=f"空头观点: {bear_argument}. 请开始你的表演。"),
        ]

        response = await llm.ainvoke(messages)
        content = self._clean_json(response.content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}\nContent: {content}")
            raise ValueError("AI 返回的数据格式不正确")

    async def react_earnings(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        old_context: Dict[str, Any],
        financial_snapshot: Dict[str, Any],
        north_star_metrics: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Two-step ReAct process:
        Step 1: Qualitative analysis with react_earnings.txt
        Step 2: Quantitative valuation with react_valuation.txt
        """
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
        )

        # === STEP 1: Qualitative Analysis ===
        template_qual = self._load_prompt("react_earnings.txt")

        # Extract old context
        company_name = old_context.get("company_name", "Unknown")
        old_radar = old_context.get("radar_scores", {})
        old_val_type = old_context.get("valuation_type", "N/A")

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
            old_essence=old_context.get("analysis_normal", {}).get("essence", "N/A"),
            period=financial_snapshot.get("period", "Unknown"),
            revenue=metrics.get("revenue", "N/A"),
            revenue_growth=metrics.get("revenue_growth_yoy", "N/A"),
            profit=metrics.get("net_profit", "N/A"),
            profit_growth=metrics.get("profit_growth_yoy", "N/A"),
            other_metrics=other_metrics,
            north_star_metrics=ns_metrics_str,
        )

        messages_qual = [
            SystemMessage(content=formatted_qual_prompt),
            HumanMessage(content="财报已更新，请开始 ReAct 推演。"),
        ]

        response_qual = await llm.ainvoke(messages_qual)
        content_qual = self._clean_json(response_qual.content)

        try:
            result_qual = json.loads(content_qual)
        except json.JSONDecodeError as e:
            print(f"Step 1 JSON Parse Error: {e}\nContent: {content_qual}")
            raise ValueError("AI 返回的数据格式不正确 (Step 1)")

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
            SystemMessage(content=formatted_val_prompt),
            HumanMessage(content="请基于以上分析结果进行定量估值。"),
        ]

        response_val = await llm.ainvoke(messages_val)
        content_val = self._clean_json(response_val.content)

        try:
            result_val = json.loads(content_val)
        except json.JSONDecodeError as e:
            print(f"Step 2 JSON Parse Error: {e}\nContent: {content_val}")
            raise ValueError("AI 返回的数据格式不正确 (Step 2)")

        # === MERGE RESULTS ===
        merged_result = {
            # From Step 1 (Qualitative)
            "react_summary": result_qual.get("react_summary", ""),
            "north_star_analysis": result_qual.get("north_star_analysis", ""),
            "new_radar_scores": result_qual.get("new_radar_scores", {}),
            "new_analysis_normal": result_qual.get("new_analysis_normal", {}),
            "master_views": result_qual.get("master_views", {}),
            "valuation_adjustment_reasoning": result_qual.get(
                "valuation_adjustment_reasoning", ""
            ),
            # From Step 2 (Quantitative)
            "valuation_type": result_val.get("valuation_type", ""),
            "valuation_params": result_val.get("valuation_params", {}),
            "valuation_explanation": result_val.get("valuation_explanation", {}),
            "fair_value_range": result_val.get("fair_value_range", {}),
            "valuation_verdict": result_val.get("valuation_verdict", "HOLD"),
            "margin_of_safety": result_val.get("margin_of_safety", ""),
            "verdict_reasoning": result_val.get("verdict_reasoning", ""),
        }

        return merged_result
