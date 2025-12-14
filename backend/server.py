from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import webbrowser
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from ai_engine import AIEngine
from utils import Storage
from config.history_schema import normalize_history_data

# Load environment variables
load_dotenv()

app = FastAPI(title="AlphaSeeker API")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper to get config from env ---
def get_env_config():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL_NAME", "gpt-4o").strip()

    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set in .env")

    return api_key, base_url, model


# --- Data Models ---


class Metric(BaseModel):
    name: str
    current_value: str
    unit: str = ""


class AnalyzeRequest(BaseModel):
    ticker: str
    price: float
    custom_metrics: List[Metric] = []


class ReactRequest(BaseModel):
    old_context: Dict[str, Any]
    financial_snapshot: Dict[str, Any]
    custom_metrics: List[Metric] = []
    price: Optional[float] = None  # Current price for saving


class UpdateHeaderRequest(BaseModel):
    ticker: str
    price: Optional[float] = None
    financial_snapshot: Dict[str, Any]


class UpdateMetricsRequest(BaseModel):
    ticker: str
    north_star_metrics: List[Dict[str, Any]]


# --- Services ---

engine = AIEngine()
storage = Storage()


# --- Routes ---


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "3.4"}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        print(
            f"[AlphaSeeker][api_analyze][start] ticker={req.ticker} price={req.price} metrics={len(req.custom_metrics or [])}"
        )
        api_key, base_url, model = get_env_config()

        # Convert Pydantic metrics to list of dicts
        metrics_dict = [m.model_dump() for m in req.custom_metrics]

        result = await engine.analyze(
            api_key=api_key,
            base_url=base_url,
            model_name=model,
            ticker=req.ticker,
            price=req.price,
            custom_metrics=metrics_dict,
        )

        # Auto-save analysis result with price (覆盖模式)
        saved = storage.save_and_replace(ticker=req.ticker, data=result, price=req.price)
        print(
            f"[AlphaSeeker][api_analyze][saved] ticker={req.ticker} ts={saved.get('timestamp')} price={req.price}"
        )

        return result
    except Exception as e:
        print(f"Error in analyze: {e}")
        raise HTTPException(status_code=502, detail=f"AI Provider Error: {str(e)}")


@app.post("/api/react")
async def react_earnings(req: ReactRequest):
    try:
        ticker_hint = (req.old_context or {}).get("ticker") if req.old_context else None
        print(
            f"[AlphaSeeker][api_react][start] ticker={ticker_hint} price={req.price} metrics={len(req.custom_metrics or [])}"
        )
        api_key, base_url, model = get_env_config()

        # Convert Pydantic metrics to list of dicts
        metrics_dict = [m.model_dump() for m in req.custom_metrics]

        result = await engine.react_earnings(
            api_key=api_key,
            base_url=base_url,
            model_name=model,
            context=req.old_context,
            financial_snapshot=req.financial_snapshot,
            north_star_metrics=metrics_dict,
        )

        # Auto-save react result with price (覆盖模式)
        ticker = result.get("ticker") or req.old_context.get("ticker", "UNKNOWN")
        saved = storage.save_and_replace(ticker=ticker, data=result, price=req.price)
        print(
            f"[AlphaSeeker][api_react][saved] ticker={ticker} ts={saved.get('timestamp')} price={req.price}"
        )

        return result
    except Exception as e:
        print(f"Error in react: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def get_history(ticker: Optional[str] = None):
    return storage.load(ticker)


@app.post("/api/save")
def save_history(item: Dict[str, Any]):
    """手动保存分析记录"""
    ticker = item.get("ticker", "UNKNOWN")
    data = item.get("data", {})
    price = item.get("price")
    timestamp = item.get("timestamp")

    if isinstance(data, dict):
        data = normalize_history_data(data, ticker=ticker)
    storage.save(ticker=ticker, data=data, price=price, timestamp=timestamp)
    print(
        f"[AlphaSeeker][api_save][saved] ticker={ticker} ts={timestamp} price={price}"
    )
    return {"status": "saved"}


@app.post("/api/update-header")
def update_header(req: UpdateHeaderRequest):
    """更新header字段（股价、营收、净利润、PE、增长率）"""
    try:
        # 获取最新记录
        latest = storage.get_latest(req.ticker)
        if not latest:
            raise HTTPException(status_code=404, detail=f"未找到ticker {req.ticker} 的记录")
        
        # 更新数据
        data = latest.get("data", {})
        if not isinstance(data, dict):
            data = {}
        
        # 更新financial_snapshot
        if "financial_snapshot" not in data:
            data["financial_snapshot"] = {}
        data["financial_snapshot"].update(req.financial_snapshot)
        
        # 确保数据格式正确
        data = normalize_history_data(data, ticker=req.ticker)
        
        # 使用覆盖模式保存
        saved = storage.save_and_replace(
            ticker=req.ticker,
            data=data,
            price=req.price if req.price is not None else latest.get("price")
        )
        print(
            f"[AlphaSeeker][api_update_header][saved] ticker={req.ticker} price={req.price}"
        )
        return {"status": "updated", "data": saved.get("data")}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in update_header: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update-metrics")
def update_metrics(req: UpdateMetricsRequest):
    """更新北极星指标"""
    try:
        # 获取最新记录
        latest = storage.get_latest(req.ticker)
        if not latest:
            raise HTTPException(status_code=404, detail=f"未找到ticker {req.ticker} 的记录")
        
        # 更新数据
        data = latest.get("data", {})
        if not isinstance(data, dict):
            data = {}
        
        # 更新north_star_metrics
        data["north_star_metrics"] = req.north_star_metrics
        
        # 确保数据格式正确
        data = normalize_history_data(data, ticker=req.ticker)
        
        # 使用覆盖模式保存
        saved = storage.save_and_replace(
            ticker=req.ticker,
            data=data,
            price=latest.get("price")
        )
        print(
            f"[AlphaSeeker][api_update_metrics][saved] ticker={req.ticker} metrics_count={len(req.north_star_metrics)}"
        )
        return {"status": "updated", "data": saved.get("data")}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in update_metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Static Files ---
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    port = 12123
    if os.environ.get("RELOAD") != "True":
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
