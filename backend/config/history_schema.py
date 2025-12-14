from typing import Any, Dict, Optional


def history_data_template(ticker: str = "") -> Dict[str, Any]:
    """
    固定化输出模板：保证 history.jsonl 的 data 在不同步骤下都拥有稳定 key。
    只在对应步骤更新这些 key 的内容，未更新的字段保持默认值或继承旧值。
    """
    return {
        "ticker": ticker or "",
        "company_name": "",
        "currency": "",
        "business_model": {},
        "moat_analysis": {},
        "radar_scores": {},
        "north_star_metrics": [],
        "analysis_normal": {},
        "analysis_broken": {},
        "master_views": {},
        "valuation_type": "",
        "valuation_params": {},
        "valuation_explanation": {},
        "react_summary": "",
        "north_star_analysis": "",
        "valuation_adjustment_reasoning": "",
        "fair_value_range": {},
        "valuation_verdict": "",
        "margin_of_safety": "",
        "verdict_reasoning": "",
        "financial_snapshot": {},
        "reasoning_trace": "",
    }


def normalize_history_data(
    data: Any, *, ticker: Optional[str] = None
) -> Dict[str, Any]:
    """
    将任意 dict 归一到固定 schema；只覆盖模板内已定义的 key，避免结构漂移。
    """
    base = history_data_template(ticker or "")
    if isinstance(data, dict):
        for k in base.keys():
            if k in data and data[k] is not None:
                base[k] = data[k]
    if ticker:
        base["ticker"] = ticker
    if not base.get("ticker") and isinstance(data, dict) and data.get("ticker"):
        base["ticker"] = data.get("ticker")
    return base
