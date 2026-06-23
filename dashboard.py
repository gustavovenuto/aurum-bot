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
                hdr = {"Authorization": f"Bearer {a['key']}"}
                data = {}
                data["earnings"] = requests.get(f"{AH_BASE}/agents/earnings", headers=hdr, timeout=10).json()
                data["profile"] = requests.get(f"{AH_BASE}/agents/me", headers=hdr, timeout=10).json()
                data["email_status"] = requests.get(f"{AH_BASE}/agents/me/email/status", headers=hdr, timeout=10).json()
                data["daily_quests"] = requests.get(f"{AH_BASE}/agents/daily-quests", headers=hdr, timeout=10).json()
                data["prediction"] = requests.get(f"{AH_BASE}/prediction/markets", headers=hdr, timeout=10).json()
                data["red_packets"] = requests.get(f"{AH_BASE}/red-packets", headers=hdr, timeout=10).json()
                data["forum"] = requests.get(f"{AH_BASE}/forum", headers=hdr, timeout=10).json()
                data["war_quests"] = requests.get(f"{AH_BASE}/alliance-war/quests", headers=hdr, timeout=10).json()
                CACHE["data"][a["name"]] = data
            except Exception as e:
                CACHE["data"][a["name"]] = {"error": str(e)}
        CACHE["last_update"] = datetime.now().isoformat()
        CACHE["logs"].append(f"[{CACHE['last_update']}] Updated {len(AGENTS)} bots")
        if len(CACHE["logs"]) > 100:
            CACHE["logs"] = CACHE["logs"][-100:]
        time.sleep(30)

threading.Thread(target=fetch_stats, daemon=True).start()

def fmt(v, d="?"):
    return v if v else d

def s(v):
    if v is None:
        return 0
    if isinstance(v, str):
        return float(v.replace(",", "")) if v.replace(".", "").replace(",", "").isdigit() else 0
    return float(v)

def render_html():
    cards = ""
    totals = {"usdc": 0, "xp": 0, "quests": 0, "wins": 0, "streak": 0, "daily_done": 0, "email_ok": 0, "discord_ok": 0, "twitter_ok": 0, "reddit_ok": 0}

    for a in AGENTS:
        d = CACHE["data"].get(a["name"], {})
        if "error" in d:
            cards += f"""<div class="card error"><div class="ch"><span class="cn">{a['name']}</span><span class="badge err">ERRO</span></div><p class="er">{d['error']}</p></div>"""
            continue

        e = d.get("earnings", {})
        p = d.get("profile", {})
        es = d.get("email_status", {})
        dq = d.get("daily_quests", {})
        rp = d.get("red_packets", {})
        pred = d.get("prediction", {})
        forum = d.get("forum", {})
        wq = d.get("war_quests", {})

        total = s(e.get("total_earned"))
        pending = s(e.get("pending_earned"))
        confirmed = s(e.get("confirmed_earned"))
        xp = e.get("xp_balance", 0)
        level = e.get("level_name", "?")
        streak = p.get("stats_snapshot", {}).get("streak", 0)
        quests = e.get("quest_submissions", 0)
        wins = e.get("quest_wins", 0)
        rank = e.get("earnings_rank", "?")
        total_agents = p.get("stats_snapshot", {}).get("total_agents", 1)

        email_ok = e.get("email_verified", False)
        discord_ok = e.get("discord_verified", False)
        twitter_ok = e.get("twitter_verified", False)
        reddit_ok = e.get("reddit_verified", False)
        email_bonus = es.get("bonus_amount_usd", 0)
        email_bonus_paid = es.get("bonus_already_paid", False)

        dq_quests = dq.get("quests", [])
        dq_done = sum(1 for q in dq_quests if q.get("completed"))
        dq_total = len(dq_quests)
        dq_bonus = dq.get("bonus_claimed", False)
        dq_bonus_pts = dq.get("bonus_earned", 0)

        bonus_bal = p.get("bonus_balance_usd", 0)
        pred_bal = p.get("prediction_balance_usd", 0)
        pred_markets = len(pred.get("data", []))
        wallet = p.get("wallet_address")
        fluxa = p.get("fluxa_agent_id")

        forum_posts = len(forum.get("data", []))
        rp_active = sum(1 for pkt in rp.get("data", []) if pkt.get("status") == "active")
        wq_open = sum(1 for q in wq.get("data", []) if q.get("status") == "open")

        totals["usdc"] += total
        totals["xp"] += s(xp)
        totals["quests"] += s(quests)
        totals["wins"] += s(wins)
        totals["streak"] += s(streak)
        totals["daily_done"] += dq_done
        if email_ok:
            totals["email_ok"] += 1
        if discord_ok:
            totals["discord_ok"] += 1
        if twitter_ok:
            totals["twitter_ok"] += 1
        if reddit_ok:
            totals["reddit_ok"] += 1

        rank_pct = round((1 - s(rank) / s(total_agents)) * 100, 1) if s(total_agents) > 0 else 0

        dq_list = "".join(
            f"""<div class="dq-item {'done' if q.get('completed') else ''}">
                <span class="dq-name">{q.get('name', q.get('id', '?'))}</span>
                <span class="dq-status">{'✓' if q.get('completed') else '○'}</span>
            </div>"""
            for q in dq_quests
        )

        cards += f"""
<div class="card">
    <div class="ch">
        <span class="cn">{a['name']}</span>
        <span class="badge lvl">Lv.{s(level) if level.isdigit() else '?'}</span>
        <span class="badge alli">{a['alliance'].upper()}</span>
        <span class="badge online">Online</span>
    </div>

    <div class="section-label">USDC</div>
    <div class="sg sg4">
        <div class="st"><span class="sl">Total</span><span class="sv gr">${total:.2f}</span></div>
        <div class="st"><span class="sl">Pending</span><span class="sv yl">${pending:.2f}</span></div>
        <div class="st"><span class="sl">Confirmado</span><span class="sv gr">${confirmed:.2f}</span></div>
        <div class="st"><span class="sl">Threshold</span><span class="sv">${s(e.get('payout_threshold', 1)):.2f}</span></div>
    </div>

    <div class="section-label">Progresso</div>
    <div class="sg sg5">
        <div class="st"><span class="sl">XP</span><span class="sv pu">{xp}</span></div>
        <div class="st"><span class="sl">Streak</span><span class="sv">{streak}d</span></div>
        <div class="st"><span class="sl">Rank</span><span class="sv">#{rank} ({rank_pct}%)</span></div>
        <div class="st"><span class="sl">Quests</span><span class="sv">{quests}</span></div>
        <div class="st"><span class="sl">Wins</span><span class="sv gr">{wins}</span></div>
    </div>

    <div class="section-label">Saldo Bonus</div>
    <div class="sg sg2">
        <div class="st"><span class="sl">Bonus Balance</span><span class="sv yl">${bonus_bal:.2f}</span></div>
        <div class="st"><span class="sl">Prediction Balance</span><span class="sv pu">${pred_bal:.2f}</span></div>
    </div>

    <div class="section-label">Daily Quests {dq_done}/{dq_total} {'★ +' + str(dq_bonus_pts) + 'XP' if dq_bonus else ''}</div>
    <div class="dq-grid">{dq_list}</div>

    <div class="section-label">Atividades</div>
    <div class="sg sg4">
        <div class="st"><span class="sl">War Quests</span><span class="sv">{wq_open} open</span></div>
        <div class="st"><span class="sl">Forum Posts</span><span class="sv">{forum_posts}</span></div>
        <div class="st"><span class="sl">Red Packets</span><span class="sv yl">{rp_active} active</span></div>
        <div class="st"><span class="sl">Pred Markets</span><span class="sv">{pred_markets}</span></div>
    </div>

    <div class="section-label">Verificações</div>
    <div class="sg sg4">
        <div class="st"><span class="sl">Email</span><span class="sv {'gr' if email_ok else 'rd'}">{'✓' if email_ok else '○'} {'$' + str(email_bonus) + ' disp' if email_ok and not email_bonus_paid else ''}</span></div>
        <div class="st"><span class="sl">Discord</span><span class="sv {'gr' if discord_ok else 'rd'}">{'✓' if discord_ok else '○'}</span></div>
        <div class="st"><span class="sl">Twitter</span><span class="sv {'gr' if twitter_ok else 'rd'}">{'✓' if twitter_ok else '○'}</span></div>
        <div class="st"><span class="sl">Reddit</span><span class="sv {'gr' if reddit_ok else 'rd'}">{'✓' if reddit_ok else '○'}</span></div>
    </div>

    <div class="section-label">Carteira</div>
    <div class="sg sg2">
        <div class="st"><span class="sl">Wallet</span><span class="sv" style="font-size:11px">{wallet or 'Não configurada'}</span></div>
        <div class="st"><span class="sl">FluxA</span><span class="sv" style="font-size:11px">{fluxa or 'Não configurado'}</span></div>
    </div>
</div>"""

    logs_html = "".join(f"<li>{l}</li>" for l in CACHE["logs"][-15:])

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aurum Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:20px; }}
h1 {{ font-size:22px; }}
.sub {{ color:#94a3b8; font-size:13px; margin:2px 0 16px; }}
.sum {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }}
.sc {{ background:#1e293b; border-radius:10px; padding:12px 18px; flex:1; min-width:130px; border:1px solid #334155; }}
.sc .l {{ color:#94a3b8; font-size:11px; }}
.sc .v {{ font-size:22px; font-weight:700; color:#22c55e; }}
.sc .v.xp {{ color:#a78bfa; }}
.sc .v.yl {{ color:#f59e0b; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:12px; }}
.card {{ background:#1e293b; border-radius:10px; padding:14px; border:1px solid #334155; }}
.card.error {{ border-color:#ef4444; }}
.ch {{ display:flex; align-items:center; gap:6px; margin-bottom:10px; flex-wrap:wrap; }}
.cn {{ font-size:15px; font-weight:600; }}
.badge {{ font-size:10px; padding:2px 7px; border-radius:8px; font-weight:600; }}
.badge.err {{ background:#7f1d1d; color:#fca5a5; }}
.badge.online {{ background:#166534; color:#86efac; }}
.badge.alli {{ background:#7c3aed; color:#ddd6fe; }}
.badge.lvl {{ background:#1e40af; color:#bfdbfe; }}
.er {{ color:#fca5a5; font-size:12px; }}
.section-label {{ font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin:10px 0 4px; }}
.sg {{ display:grid; gap:4px; }}
.sg2 {{ grid-template-columns:repeat(2,1fr); }}
.sg4 {{ grid-template-columns:repeat(4,1fr); }}
.sg5 {{ grid-template-columns:repeat(5,1fr); }}
.st {{ text-align:center; padding:5px 3px; background:#0f172a; border-radius:6px; }}
.sl {{ display:block; color:#94a3b8; font-size:9px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.sv {{ font-size:13px; font-weight:600; }}
.sv.gr {{ color:#22c55e; }}
.sv.yl {{ color:#f59e0b; }}
.sv.pu {{ color:#a78bfa; }}
.sv.rd {{ color:#f87171; }}
.dq-grid {{ display:flex; flex-wrap:wrap; gap:4px; }}
.dq-item {{ display:flex; align-items:center; gap:6px; background:#0f172a; padding:4px 8px; border-radius:6px; font-size:11px; }}
.dq-item.done {{ background:#166534; }}
.dq-name {{ flex:1; }}
.dq-status {{ font-weight:700; color:#22c55e; }}
.logs {{ background:#1e293b; border-radius:10px; padding:14px; margin-top:16px; border:1px solid #334155; }}
.logs h2 {{ font-size:13px; margin-bottom:8px; }}
.logs ul {{ list-style:none; font-family:monospace; font-size:11px; color:#94a3b8; }}
.logs li {{ padding:1px 0; }}
.ft {{ text-align:center; color:#475569; font-size:11px; margin-top:16px; }}
</style>
<meta http-equiv="refresh" content="15">
</head>
<body>
<h1>Aurum Dashboard</h1>
<p class="sub">{len(AGENTS)} bots • Auto-atualiza 15s • Última: {CACHE['last_update'] or '...'}</p>
<div class="sum">
    <div class="sc"><div class="l">USDC Total</div><div class="v">${totals['usdc']:.2f}</div></div>
    <div class="sc"><div class="l">XP Total</div><div class="v xp">{totals['xp']}</div></div>
    <div class="sc"><div class="l">Quest Wins</div><div class="v">{totals['wins']}</div></div>
    <div class="sc"><div class="l">Streak Média</div><div class="v yl">{totals['streak']/len(AGENTS):.1f}d</div></div>
    <div class="sc"><div class="l">Email</div><div class="v">{totals['email_ok']}/{len(AGENTS)}</div></div>
    <div class="sc"><div class="l">Daily Quests</div><div class="v yl">{totals['daily_done']}/15</div></div>
</div>
<div class="grid">{cards}</div>
<div class="logs">
    <h2>Atividade</h2>
    <ul>{logs_html}</ul>
</div>
<div class="ft">Dashboards AgentHansa • Dados atualizados a cada 30s</div>
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
