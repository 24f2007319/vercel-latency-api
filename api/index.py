from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import List
import json

app = FastAPI()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Expose-Headers": "Access-Control-Allow-Origin",
}

DATA_FILE = Path(__file__).parent / "q-vercel-latency.json"
with open(DATA_FILE) as f:
    telemetry_data = json.load(f)

class AnalyticsRequest(BaseModel):
    regions: List[str]
    threshold_ms: int

@app.get("/api")
def read_root():
    return JSONResponse({"status": "ok"}, headers=CORS_HEADERS)

@app.post("/api")
def analyze_latency(request: AnalyticsRequest):
    results = {}
    for region in request.regions:
        rows = [r for r in telemetry_data if r.get("region") == region]
        if not rows:
            results[region] = {"avg_latency":0,"p95_latency":0,"avg_uptime":0,"breaches":0}
            continue
        latencies = sorted([r["latency_ms"] for r in rows])
        uptimes = [r["uptime_pct"] for r in rows]
        n = len(latencies)
        idx = (n-1)*0.95
        lo = int(idx)
        p95 = latencies[lo]+(idx-lo)*(latencies[lo+1]-latencies[lo]) if lo+1 < n else latencies[lo]
        results[region] = {
            "avg_latency": round(sum(latencies)/n, 2),
            "p95_latency": round(p95, 2),
            "avg_uptime": round(sum(uptimes)/len(uptimes), 3),
            "breaches": sum(1 for lat in latencies if lat > request.threshold_ms),
        }
    return JSONResponse({"regions": results}, headers=CORS_HEADERS)

@app.options("/api")
def options_handler():
    return JSONResponse({}, headers=CORS_HEADERS)
