#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# Orchestrix AI — Live Demo Script
# Run: bash scripts/demo.sh
# Requires: curl, jq, server running on :8001
# ──────────────────────────────────────────────────────────────────

set -euo pipefail
API="http://localhost:8001"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}═══ $1 ═══${NC}\n"; }
info() { echo -e "${GREEN}→${NC} $1"; }
warn() { echo -e "${YELLOW}→${NC} $1"; }
wait_for() { sleep "${1:-2}"; }

# ── 1. Health Check ──────────────────────────────────────────────
step "1/7  Health Check"
curl -s "$API/health" | jq .
info "AI service is alive"

# ── 2. Analyze an Incident ──────────────────────────────────────
step "2/7  Incident Analysis"
info "Sending incident for root cause analysis..."
RESULT=$(curl -s -X POST "$API/ai/analyze-incident" \
  -H "Content-Type: application/json" \
  -d '{"incident_id": "demo-001", "time_range": "last_10_minutes"}')
echo "$RESULT" | jq '{incident_type, summary, root_cause, source, quality}'
info "Analysis source: $(echo "$RESULT" | jq -r '.source') (ai = GPT-4o, rule_based = fallback)"

# ── 3. Anomaly Detection ────────────────────────────────────────
step "3/7  Anomaly Detection"
curl -s -X POST "$API/ai/detect-anomalies" \
  -H "Content-Type: application/json" \
  -d '{"time_range": "last_10_minutes", "anomaly_type": "threshold"}' | jq '{anomalies: [.anomalies[] | {metric, value, severity}], summary}'
info "Threshold + z-score anomaly detection"

# ── 4. RAG Search ────────────────────────────────────────────────
step "4/7  RAG Search"
curl -s -X POST "$API/ai/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "failed jobs with high CPU"}' | jq '{query, answer, sources: (.sources | length)}'
info "Keyword retrieval over live telemetry"

# ── 5. Prioritize ───────────────────────────────────────────────
step "5/7  Incident Prioritization"
curl -s -X POST "$API/ai/prioritize" \
  -H "Content-Type: application/json" \
  -d '{"time_range": "last_10_minutes"}' | jq '{ranked_items: [.ranked_items[:3][] | {type, title, priority}]}'
info "Events ranked by severity and impact"

# ── 6. Replay Mode ──────────────────────────────────────────────
step "6/7  Replay / Debug Mode"
info "Submitting custom telemetry for reproducible analysis..."
curl -s -X POST "$API/ai/replay-incident" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"id": "e1", "timestamp": "2026-04-03T10:00:00Z", "type": "deployment", "source": "k8s", "message": "Deployed v2.4.1", "severity": "info"},
      {"id": "e2", "timestamp": "2026-04-03T10:03:00Z", "type": "error", "source": "worker", "message": "OOMKilled", "severity": "critical"}
    ],
    "jobs": [],
    "alerts": [
      {"id": "a1", "timestamp": "2026-04-03T10:02:00Z", "severity": "critical", "source": "prometheus", "message": "Memory > 90%", "metric": "container_memory_usage"}
    ],
    "metrics": []
  }' | jq '{incident_type, root_cause, correlations: (.correlations | length), quality}'
info "Replay uses your data — no live backend needed"

# ── 7. Live Monitoring (SSE) ────────────────────────────────────
step "7/7  Live Monitoring (SSE)"
info "Streaming 3 snapshots from $API/ai/live ..."
timeout 16 curl -s -N "$API/ai/live" 2>/dev/null | head -12 || true
echo ""
info "SSE stream pushes system health every 5s"

echo ""
echo -e "${BOLD}Demo complete${NC} — Orchestrix AI: correlate → classify → reason → recommend"
