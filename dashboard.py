import requests, time, threading, json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

CACHE = {"data": {}, "logs": [], "last_update": None}

AGENTS = [
    {"name": "Aurum",    "key": "tabb_5Eq9iYsuuxuarP2SPxuPM448062UvxzbYXHa0HYKl20", "alliance": "red"},
    {"name": "Aurum-02", "key": "tabb_LdisJ3cU8016BbavZ9x8He1-ihBIejMibVZjWSaZpG8", "alliance": "red"},
    {"name": "Aurum-03", "key": "tabb_t77U52PUrs0QyxMqzz0VQm29dNjqDl78-UgKLsjpJt8", "alliance": "red"},
]

AH_BASE = "https://www.agenthansa.com/api"

def fetch_stats():
    while True:
        for a in AGENTS:
            try:
                h = {"Authorization": f"Bearer {a['key']}"}
                ear = requests.get(f"{AH_BASE}/agents/earnings", headers=h, timeout=10).json()
                profile = requests.get(f"{AH_BASE}/agents/me", headers=h, timeout=10).json()
                email = requests.get(f"{AH_BASE}/agents/me/email/status", headers=h, timeout=10).json()
                dq = requests.get(f"{AH_BASE}/agents/daily-quests", headers=h, timeout=10).json()
                pred = requests.get(f"{AH_BASE}/prediction/markets", headers=h, timeout=10).json()
                packets = requests.get(f"{AH_BASE}/red-packets", headers=h, timeout=10).json()
                CACHE["data"][a["name"]] = {
                    "earnings": ear, "profile": profile, "email": email,
                    "daily_quests": dq, "prediction": pred, "red_packets": packets
                }
            except Exception as e:
                CACHE["data"][a["name"]] = {"earnings": {}, "profile": {}, "email": {}, "daily_quests": {}, "prediction": {}, "red_packets": {}, "error": str(e)}
        CACHE["last_update"] = datetime.now().isoformat()
        CACHE["logs"].append(f"[{CACHE['last_update']}] Atualizado {len(AGENTS)} bots")
        if len(CACHE["logs"]) > 100:
            CACHE["logs"] = CACHE["logs"][-100:]
        time.sleep(30)

threading.Thread(target=fetch_stats, daemon=True).start()

def render_html():
    agents_html = ""
    total_pred = 0
    total_daily = 0
    total_email = 0
    total_packets = 0

    for a in AGENTS:
        d = CACHE["data"].get(a["name"], {})
        if "error" in d:
            agents_html += f"""
            <div class="agent-card error">
                <div class="agent-header"><span class="agent-name">{a['name']}</span><span class="status-badge error">ERRO</span></div>
                <p class="error-msg">{d['error']}</p>
            </div>"""
            continue
        e = d.get("earnings", {})
        p = d.get("profile", {})
        em = d.get("email", {})
        dq = d.get("daily_quests", {}).get("data", [])
        pred = d.get("prediction", {})
        rp = d.get("red_packets", {}).get("data", [])

        streak = p.get("stats_snapshot", {}).get("streak", "?")
        xp = e.get("xp_balance", 0)
        total = float(e.get("total_earned", 0))
        pending = float(e.get("pending_earned", 0))
        confirmed = float(e.get("confirmed_earned", 0))
        quests = e.get("quest_submissions", 0)
        wins = e.get("quest_wins", 0)
        rank = e.get("earnings_rank", "?")
        level = e.get("level_name", "?")
        email_ok = em.get("verified", False)
        dq_done = sum(1 for q in dq if q.get("completed"))
        active_packets = sum(1 for pkt in rp if pkt.get("status") == "active")
        pred_markets = len(pred.get("data", []))

        if email_ok:
            total_email += 1
        total_daily += dq_done
        total_pred += pred_markets

        agents_html += f"""
        <div class="agent-card">
            <div class="agent-header">
                <span class="agent-name">{a['name']}</span>
                <span class="status-badge online">Online</span>
                <span class="alliance-badge">{a['alliance'].upper()}</span>
            </div>
            <div class="stats-grid">
                <div class="stat"><span class="stat-label">USDC Total</span><span class="stat-value">${total:.2f}</span></div>
                <div class="stat"><span class="stat-label">Pending</span><span class="stat-value pending">${pending:.2f}</span></div>
                <div class="stat"><span class="stat-label">Confirmado</span><span class="stat-value confirmed">${confirmed:.2f}</span></div>
                <div class="stat"><span class="stat-label">XP</span><span class="stat-value">{xp}</span></div>
                <div class="stat"><span class="stat-label">Level</span><span class="stat-value">{level}</span></div>
                <div class="stat"><span class="stat-label">Streak</span><span class="stat-value">{streak} dias</span></div>
                <div class="stat"><span class="stat-label">Quests</span><span class="stat-value">{quests}</span></div>
                <div class="stat"><span class="stat-label">Wins</span><span class="stat-value">{wins}</span></div>
                <div class="stat"><span class="stat-label">Rank</span><span class="stat-value">{rank}</span></div>
                <div class="stat"><span class="stat-label">Email</span><span class="stat-value {'ok' if email_ok else 'no'}">{'Verificado' if email_ok else 'Pendente'}</span></div>
                <div class="stat"><span class="stat-label">Daily Quests</span><span class="stat-value">{dq_done}/5</span></div>
                <div class="stat"><span class="stat-label">Mercados</span><span class="stat-value">{pred_markets}</span></div>
                <div class="stat"><span class="stat-label">Red Packets</span><span class="stat-value">{active_packets}</span></div>
            </div>
        </div>"""

    logs_html = "".join(f"<li>{log}</li>" for log in CACHE["logs"][-20:])
    total_usdc = sum(
        float(CACHE["data"].get(a["name"], {}).get("earnings", {}).get("total_earned", 0))
        for a in AGENTS if "earnings" in CACHE["data"].get(a["name"], {})
    )

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aurum Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:20px; }}
h1 {{ font-size:24px; margin-bottom:5px; }}
.subtitle {{ color:#94a3b8; font-size:14px; margin-bottom:20px; }}
.summary {{ display:flex; gap:20px; margin-bottom:20px; flex-wrap:wrap; }}
.summary-card {{ background:#1e293b; padding:15px 25px; border-radius:12px; flex:1; min-width:150px; }}
.summary-card .label {{ color:#94a3b8; font-size:12px; }}
.summary-card .value {{ font-size:28px; font-weight:700; color:#22c55e; }}
.agents-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(350px,1fr)); gap:15px; }}
.agent-card {{ background:#1e293b; border-radius:12px; padding:15px; border:1px solid #334155; }}
.agent-card.error {{ border-color:#ef4444; }}
.agent-header {{ display:flex; align-items:center; gap:10px; margin-bottom:12px; }}
.agent-name {{ font-size:16px; font-weight:600; }}
.status-badge {{ font-size:11px; padding:2px 8px; border-radius:10px; }}
.status-badge.online {{ background:#166534; color:#86efac; }}
.status-badge.error {{ background:#7f1d1d; color:#fca5a5; }}
.alliance-badge {{ font-size:10px; background:#7c3aed; padding:2px 8px; border-radius:10px; margin-left:auto; }}
.stats-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }}
.stat {{ text-align:center; padding:6px; background:#0f172a; border-radius:8px; }}
.stat-label {{ display:block; color:#94a3b8; font-size:10px; }}
.stat-value {{ font-size:14px; font-weight:600; }}
.stat-value.pending {{ color:#f59e0b; }}
.stat-value.confirmed {{ color:#22c55e; }}
.stat-value.ok {{ color:#22c55e; }}
.stat-value.no {{ color:#f87171; }}
.error-msg {{ color:#fca5a5; font-size:12px; }}
.logs {{ background:#1e293b; border-radius:12px; padding:15px; margin-top:20px; border:1px solid #334155; }}
.logs h2 {{ font-size:14px; margin-bottom:10px; }}
.logs ul {{ list-style:none; font-family:monospace; font-size:11px; color:#94a3b8; }}
.logs li {{ padding:2px 0; }}
.footer {{ text-align:center; color:#475569; font-size:11px; margin-top:20px; }}
.last-update {{ color:#64748b; font-size:12px; }}
</style>
<meta http-equiv="refresh" content="15">
</head>
<body>
<h1>Aurum Dashboard</h1>
<p class="subtitle">{len(AGENTS)} bots • Dados atualizados automaticamente (15s)</p>
<div class="summary">
    <div class="summary-card">
        <div class="label">USDC Total</div>
        <div class="value">${total_usdc:.2f}</div>
    </div>
    <div class="summary-card">
        <div class="label">Online</div>
        <div class="value" style="color:#22c55e">{sum(1 for a in AGENTS if a['name'] in CACHE['data'] and 'error' not in CACHE['data'][a['name']])}/{len(AGENTS)}</div>
    </div>
    <div class="summary-card">
        <div class="label">Emails Verificados</div>
        <div class="value" style="color:#22c55e">{total_email}/{len(AGENTS)}</div>
    </div>
    <div class="summary-card">
        <div class="label">Daily Quests Hoje</div>
        <div class="value" style="color:#f59e0b">{total_daily}</div>
    </div>
    <div class="summary-card">
        <div class="label">Previsões Hoje</div>
        <div class="value" style="color:#a78bfa">{total_pred}</div>
    </div>
    <div class="summary-card">
        <div class="label">Última Atualização</div>
        <div class="value" style="font-size:14px;color:#94a3b8">{CACHE['last_update'] or '...'}</div>
    </div>
</div>
<div class="agents-grid">{agents_html}</div>
<div class="logs">
    <h2>Ultimas atividades</h2>
    <ul>{logs_html}</ul>
</div>
<div class="footer">Auto-atualiza a cada 15s • Dados via AgentHansa API</div>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_html().encode("utf-8"))
    def log_message(self, *a):
        pass

print(f"\n{'='*40}")
print(f"  Aurum Dashboard rodando!")
print(f"  Acesse: http://localhost:5000")
print(f"{'='*40}\n")
HTTPServer(("0.0.0.0", 5000), Handler).serve_forever()
