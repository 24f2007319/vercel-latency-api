
from http.server import BaseHTTPRequestHandler
import json
import math
from pathlib import Path
from statistics import mean

DATA_FILE = Path(__file__).resolve().parent.parent / "q-vercel-latency.json"


def find_records(data):
    """Find telemetry records inside a JSON list or nested dictionary."""
    records = []

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            keys = {str(k).lower() for k in value}
            if (
                "region" in keys
                and any(k in keys for k in (
                    "latency_ms", "latency", "response_time_ms"
                ))
            ):
                records.append(value)
            else:
                for item in value.values():
                    if isinstance(item, (list, dict)):
                        walk(item)

    walk(data)
    return records


def get_value(record, *names):
    lowered = {str(k).lower(): v for k, v in record.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def percentile95(values):
    values = sorted(values)
    # Nearest-rank 95th percentile
    return values[max(0, math.ceil(0.95 * len(values)) - 1)]


class handler(BaseHTTPRequestHandler):
    def send_json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            regions = request["regions"]
            threshold = float(request.get("threshold_ms", 180))

            with open(DATA_FILE, encoding="utf-8") as file:
                data = json.load(file)

            records = find_records(data)
            results = []

            for region in regions:
                selected = [
                    row for row in records
                    if str(get_value(row, "region")).lower()
                    == str(region).lower()
                ]

                if not selected:
                    self.send_json(400, {
                        "error": f"No telemetry records found for {region}"
                    })
                    return

                latencies = [
                    float(get_value(row, "latency_ms", "latency",
                                    "response_time_ms"))
                    for row in selected
                ]

                uptimes = [
                    float(get_value(row, "uptime", "uptime_pct",
                                    "uptime_percent", "availability"))
                    for row in selected
                ]

                results.append({
                    "region": region,
                    "avg_latency": mean(latencies),
                    "p95_latency": percentile95(latencies),
                    "avg_uptime": mean(uptimes),
                    "breaches": sum(x > threshold for x in latencies)
                })

            self.send_json(200, {"results": results})

        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

