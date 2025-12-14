import json
import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser


_parser = JsonOutputParser()


def parse_llm_json(text: str) -> Any:
    """
    通用 LLM JSON 解析：
    - 优先用 LangChain JsonOutputParser
    - 兼容 ```json fenced code block
    - 允许输出前后夹杂少量文字（提取第一个 JSON 对象/数组）
    """
    raw = (text or "").strip()

    # 1) LangChain parser (best effort)
    try:
        return _parser.parse(raw)
    except Exception:
        pass

    # 2) Strip markdown code fences
    cleaned = raw
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # 3) Try LangChain markdown json helper (if available)
    try:
        from langchain_core.utils.json import parse_json_markdown  # type: ignore

        return parse_json_markdown(cleaned)
    except Exception:
        pass

    # 4) Extract first JSON object/array substring
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if m:
        candidate = m.group(1)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 5) Raw json.loads as last attempt
    try:
        return json.loads(cleaned)
    except Exception as e:
        snippet = cleaned[:800]
        raise ValueError(
            f"AI 返回的数据格式不正确，无法解析为 JSON: {e}. content_snippet={snippet!r}"
        )


def get_json_format_instructions() -> str:
    """给 prompt 注入的 JSON 格式约束（LangChain 官方格式指令）。"""
    return _parser.get_format_instructions()
