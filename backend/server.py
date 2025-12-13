from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import webbrowser
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from ai_engine import AIEngine

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
    # Config is now managed via .env
    ticker: str
    price: float
    custom_metrics: List[Metric] = []


class ChallengeRequest(BaseModel):
    # Config is now managed via .env
    context: Dict[str, Any]  # Full analysis JSON
    bear_argument: str


class ReactRequest(BaseModel):
    # Config is now managed via .env
    old_context: Dict[str, Any]
    financial_snapshot: Dict[str, Any]
    custom_metrics: List[Metric] = []


class HistoryItem(BaseModel):
    timestamp: str
    ticker: str
    data: Dict[str, Any]


# --- Services ---

engine = AIEngine()
DATA_FILE = Path(__file__).parent / "data" / "history.jsonl"


class Storage:
    @staticmethod
    def save(item: Dict[str, Any]):
        with open(DATA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    @staticmethod
    def load(ticker_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        if not DATA_FILE.exists():
            return []
        results = []
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if ticker_filter and data.get("ticker") != ticker_filter:
                            continue
                        results.append(data)
                    except:
                        continue
        return results[::-1]  # Newest first


# --- Routes ---


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "3.3"}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    try:
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

        # Auto-save analysis result
        save_item = {
            "timestamp": datetime.now().isoformat(),
            "ticker": req.ticker,
            "data": result,
        }
        Storage.save(save_item)

        return result
    except Exception as e:
        print(f"Error in analyze: {e}")
        # Return HTTP 502 Bad Gateway for upstream API errors, with detailed message
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
        api_key, base_url, model = get_env_config()

        # Convert Pydantic metrics to list of dicts
        metrics_dict = [m.model_dump() for m in req.custom_metrics]

        result = await engine.react_earnings(
            api_key=api_key,
            base_url=base_url,
            model_name=model,
            old_context=req.old_context,
            financial_snapshot=req.financial_snapshot,
            north_star_metrics=metrics_dict,
        )

        # Auto-save react result
        # We need to ensure we can identify which company this is for
        ticker = req.old_context.get("ticker", "UNKNOWN")
        save_item = {
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "data": result,
            "type": "react_update",
        }
        Storage.save(save_item)

        return result
    except Exception as e:
        print(f"Error in react: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def get_history(ticker: Optional[str] = None):
    return Storage.load(ticker)


@app.post("/api/save")
def save_history(item: Dict[str, Any]):
    # Add timestamp if not present
    if "timestamp" not in item:
        item["timestamp"] = datetime.now().isoformat()

    Storage.save(item)
    return {"status": "saved"}


# --- Static Files ---
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    # Auto-open browser on startup
    port = 12123
    if os.environ.get("RELOAD") != "True":  # Avoid opening twice on reload
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
