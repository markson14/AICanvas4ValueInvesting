import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Default data file path
DEFAULT_DATA_FILE = Path(__file__).parent.parent / "data" / "history.jsonl"


class Storage:
    """通用 JSONL 存储类，用于保存和加载分析记录"""

    def __init__(self, data_file: Path = DEFAULT_DATA_FILE):
        self.data_file = data_file
        # Ensure data directory exists
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        ticker: str,
        data: Dict[str, Any],
        price: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        保存一条分析记录到 JSONL 文件

        Args:
            ticker: 股票代码
            data: 分析数据（完整的 JSON 对象）
            price: 当前股价（可选）
            timestamp: 时间戳（可选，默认为当前时间）

        Returns:
            保存的完整记录
        """
        record = {
            "timestamp": timestamp or datetime.now().isoformat(),
            "ticker": ticker,
            "price": price,
            "data": data,
        }

        with open(self.data_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def load(self, ticker_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        从 JSONL 文件加载分析记录

        Args:
            ticker_filter: 可选的股票代码过滤器

        Returns:
            记录列表（最新的在前）
        """
        if not self.data_file.exists():
            return []

        results = []
        with open(self.data_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        # Backward compatibility: old records may not have 'price'
                        if "price" not in record:
                            record["price"] = None
                        # Backward compatibility: ensure record.data.ticker exists for react flow
                        data = record.get("data")
                        if isinstance(data, dict):
                            if not data.get("ticker") and record.get("ticker"):
                                data["ticker"] = record.get("ticker")
                            if not record.get("ticker") and data.get("ticker"):
                                record["ticker"] = data.get("ticker")
                        if ticker_filter and record.get("ticker") != ticker_filter:
                            continue
                        results.append(record)
                    except json.JSONDecodeError:
                        continue

        return results[::-1]  # Newest first

    def get_latest(self, ticker: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取最新的一条记录

        Args:
            ticker: 可选的股票代码过滤器

        Returns:
            最新记录，如果不存在则返回 None
        """
        records = self.load(ticker)
        return records[0] if records else None

    def get_unique_tickers(self) -> List[str]:
        """
        获取所有不重复的股票代码列表

        Returns:
            股票代码列表
        """
        records = self.load()
        return list(set(r.get("ticker", "") for r in records if r.get("ticker")))

    def save_and_replace(
        self,
        ticker: str,
        data: Dict[str, Any],
        price: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        保存一条分析记录，并删除该ticker的所有旧记录（覆盖模式）
        
        Args:
            ticker: 股票代码
            data: 分析数据（完整的 JSON 对象）
            price: 当前股价（可选）
            timestamp: 时间戳（可选，默认为当前时间）
            
        Returns:
            保存的完整记录
        """
        # 读取所有记录
        all_records = []
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            # 只保留不是当前ticker的记录
                            if record.get("ticker") != ticker:
                                all_records.append(record)
                        except json.JSONDecodeError:
                            continue
        
        # 创建新记录
        new_record = {
            "timestamp": timestamp or datetime.now().isoformat(),
            "ticker": ticker,
            "price": price,
            "data": data,
        }
        
        # 写入所有记录（旧记录 + 新记录）
        with open(self.data_file, "w", encoding="utf-8") as f:
            for record in all_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.write(json.dumps(new_record, ensure_ascii=False) + "\n")
        
        return new_record


# 全局默认实例
storage = Storage()
