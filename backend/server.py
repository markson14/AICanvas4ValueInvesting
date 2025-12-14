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


class ChallengeRequest(BaseModel):
    context: Dict[str, Any]
    bear_argument: str


class ReactRequest(BaseModel):
    old_context: Dict[str, Any]
    financial_snapshot: Dict[str, Any]
    custom_metrics: List[Metric] = []
    price: Optional[float] = None  # Current price for saving


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

        # Auto-save analysis result with price
        saved = storage.save(ticker=req.ticker, data=result, price=req.price)
        print(
            f"[AlphaSeeker][api_analyze][saved] ticker={req.ticker} ts={saved.get('timestamp')} price={req.price}"
        )

        return result
    except Exception as e:
        print(f"Error in analyze: {e}")
        raise HTTPException(status_code=502, detail=f"AI Provider Error: {str(e)}")


@app.post("/api/challenge")
async def challenge(req: ChallengeRequest):
    try:
        api_key, base_url, model = get_env_config()

        result = await engine.challenge(
            api_key=api_key,
            base_url=base_url,
            model_name=model,
            context=req.context,
            bear_argument=req.bear_argument,
        )
        return result
    except Exception as e:
        print(f"Error in challenge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        # Auto-save react result with price
        ticker = result.get("ticker") or req.old_context.get("ticker", "UNKNOWN")
        saved = storage.save(ticker=ticker, data=result, price=req.price)
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

    storage.save(ticker=ticker, data=data, price=price, timestamp=timestamp)
    return {"status": "saved"}


# --- Static Files ---
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    port = 12123
    if os.environ.get("RELOAD") != "True":
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
