import requests, time, threading, json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

CACHE = {"data": {}, "logs": [], "last_update": None, "errors": {}, "next_runs": {}}

AGENTS = [
    {"name": "Aurum",    "key": "tabb_5Eq9iYsuuxuarP2SPxuPM448062UvxzbYXHa0HYKl20", "alliance": "red"},
    {"name": "Aurum-02", "key": "tabb_LdisJ3cU8016BbavZ9x8He1-ihBIejMibVZjWSaZpG8", "alliance": "red"},
    {"name": "Aurum-03", "key": "tabb_t77U52PUrs0QyxMqzz0VQm29dNjqDl78-UgKLsjpJt8", "alliance": "red"},
]

AH_BASE = "https://www.agenthansa.com/api"

def safe_get(url, headers, timeout=10):
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        return r.json(), None
    except Exception as e:
        return {}, str(e)

def fetch_stats():
    while True:
        for a in AGENTS:
            hdr = {"Authorization": f"Bearer {a['key']}"}
            data = {}
            errs = {}
            for name, url in [
                ("earnings", f"{AH_BASE}/agents/earnings"),
                ("profile", f"{AH_BASE}/agents/me"),
                ("email_status", f"{AH_BASE}/agents/me/email/status"),
                ("daily_quests", f"{AH_BASE}/agents/daily-quests"),
                ("prediction", f"{AH_BASE}/prediction/markets"),
                ("red_packets", f"{AH_BASE}/red-packets"),
                ("forum", f"{AH_BASE}/forum"),
                ("war_quests", f"{AH_BASE}/alliance-war/quests"),
            ]:
                result, error = safe_get(url, hdr)
                data[name] = result
                if error:
                    errs[name] = error
            CACHE["data"][a["name"]] = data
            if errs:
                CACHE["errors"][a["name"]] = errs
            elif a["name"] in CACHE["errors"]:
                del CACHE["errors"][a["name"]]
        CACHE["last_update"] = datetime.now().isoformat()
        CACHE["logs"].append(f"[{CACHE['last_update']}] Updated {len(AGENTS)} bots")
        if len(CACHE["logs"]) > 100:
            CACHE["logs"] = CACHE["logs"][-100:]
        time.sleep(30)

threading.Thread(target=fetch_stats, daemon=True).start()

def s(v):
    if v is None:
        return 0
    if isinstance(v, str):
        try:
            return float(v)
        except:
            return 0
    return float(v)

def render_html():
    cards = ""
    actions_global = []
    totals = {"usdc": 0, "xp": 0, "quests": 0, "wins": 0, "streak": 0, "daily_done": 0,
              "email": 0, "discord": 0, "twitter": 0, "reddit": 0}

    for a in AGENTS:
        d = CACHE["data"].get(a["name"], {})
        errs = CACHE["errors"].get(a["name"], {})

        if "error" in d:
            cards += f"""<div class="card error"><div class="ch"><span class="cn">{a['name']}</span><span class="badge err">OFFLINE</span></div><p class="er">{d['error']}</p></div>"""
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
        level_name = e.get("level_name", "?")
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

        dq_quests = dq.get("quests", [])
        dq_done = sum(1 for q in dq_quests if q.get("completed"))
        dq_total = len(dq_quests) or 5
        dq_bonus = dq.get("bonus_claimed", False)
        dq_bonus_pts = dq.get("bonus_earned", 0)

        bonus_bal = s(p.get("bonus_balance_usd", 0))
        pred_bal = s(p.get("prediction_balance_usd", 0))
        pred_markets = len(pred.get("markets", []))
        wallet = p.get("wallet_address")
        fluxa = p.get("fluxa_agent_id")
        rank_pct = round((1 - s(rank) / s(total_agents)) * 100, 1) if s(total_agents) > 0 else 0

        forum_posts = len(forum.get("posts", []))
        rp_active = len(rp.get("active", []))
        wq_open = sum(1 for q in wq.get("quests", []) if q.get("status") == "open")

        totals["usdc"] += total
        totals["xp"] += s(xp)
        totals["quests"] += s(quests)
        totals["wins"] += s(wins)
        totals["streak"] += s(streak)
        totals["daily_done"] += dq_done
        if email_ok:
            totals["email"] += 1
        if discord_ok:
            totals["discord"] += 1
        if twitter_ok:
            totals["twitter"] += 1
        if reddit_ok:
            totals["reddit"] += 1

        blocked = []
        if not discord_ok:
            blocked.append("Discord")
        if not twitter_ok:
            blocked.append("Twitter")
        if not reddit_ok:
            blocked.append("Reddit")
        if not wallet:
            blocked.append("Wallet FluxA")
        if not email_ok:
            blocked.append("Email (click link!)")

        pausado = "paused" in str(e.get("detail", "")).lower() or "paused" in str(p.get("detail", "")).lower()

        dq_list = "".join(
            f"""<div class="dq-item {'done' if q.get('completed') else ''}">
                <span class="dq-name">{q.get('name', q.get('id', '?'))}</span>
                <span class="dq-status">{'✓' if q.get('completed') else '○'}</span>
            </div>"""
            for q in dq_quests
        )

        error_list = "".join(
            f"<div class='api-err'>{k}: {v[:80]}</div>"
            for k, v in errs.items()
        )

        if errs:
            actions_global.append(f"{a['name']}: API errors — {', '.join(errs.keys())}")

        cards += f"""
<div class="card{' paused' if pausado else ''}">
    <div class="ch">
        <span class="cn">{a['name']}</span>
        <span class="badge lvl">{level_name}</span>
        <span class="badge alli">{a['alliance'].upper()}</span>
        <span class="badge {'online' if not errs else 'err'}">{'ON' if not errs else 'ERR'}</span>
        {f'<span class="badge paused-badge">PAUSADO</span>' if pausado else ''}
    </div>
    {error_list}

    <div class="section-label">USDC</div>
    <div class="sg sg4">
        <div class="st"><span class="sl">Total</span><span class="sv gr">${total:.4f}</span></div>
        <div class="st"><span class="sl">Pending</span><span class="sv yl">${pending:.4f}</span></div>
        <div class="st"><span class="sl">Confirmado</span><span class="sv gr">${confirmed:.4f}</span></div>
        <div class="st"><span class="sl">Libera em</span><span class="sv">${s(e.get('payout_threshold', 1)):.2f}</span></div>
    </div>

    <div class="section-label">Progresso</div>
    <div class="sg sg5">
        <div class="st"><span class="sl">XP</span><span class="sv pu">{xp}</span></div>
        <div class="st"><span class="sl">Streak</span><span class="sv">{streak}d</span></div>
        <div class="st"><span class="sl">Rank</span><span class="sv">#{rank} ({rank_pct}%)</span></div>
        <div class="st"><span class="sl">Quests</span><span class="sv">{quests}</span></div>
        <div class="st"><span class="sl">Wins</span><span class="sv gr">{wins}</span></div>
    </div>

    <div class="section-label">Bônus</div>
    <div class="sg sg2">
        <div class="st"><span class="sl">Bonus Balance</span><span class="sv yl">${bonus_bal:.2f}</span></div>
        <div class="st"><span class="sl">Prediction Bal.</span><span class="sv pu">${pred_bal:.2f}</span></div>
    </div>

    <div class="section-label">Daily Quests {dq_done}/{dq_total} {f'★ +{dq_bonus_pts}XP' if dq_bonus else ''}</div>
    <div class="dq-grid">{dq_list}</div>

    <div class="section-label">Atividades</div>
    <div class="sg sg4">
        <div class="st{r' na' if wq_open == 0 else ' gr'}"><span class="sl">War Quests</span><span class="sv">{wq_open} abertas</span></div>
        <div class="st"><span class="sl">Forum Posts</span><span class="sv">{forum_posts}</span></div>
        <div class="st{r' na' if rp_active == 0 else ' gr'}"><span class="sl">Red Packets</span><span class="sv">{rp_active} ativos</span></div>
        <div class="st"><span class="sl">Previsões</span><span class="sv">{pred_markets} mercados</span></div>
    </div>

    <div class="section-label">Verificações</div>
    <div class="sg sg4">
        <div class="st"><span class="sl">Email</span><span class="sv {'gr' if email_ok else 'rd'}">{'✓' if email_ok else '○'} {f'${email_bonus:.2f} disp' if email_ok else ''}</span></div>
        <div class="st{r' rd' if not discord_ok else ' gr'}"><span class="sl">Discord</span><span class="sv">{'✓' if discord_ok else '○ bloqueia $'}</span></div>
        <div class="st{r' rd' if not twitter_ok else ' gr'}"><span class="sl">Twitter</span><span class="sv">{'✓' if twitter_ok else '○ bloqueia $'}</span></div>
        <div class="st{r' rd' if not reddit_ok else ' gr'}"><span class="sl">Reddit</span><span class="sv">{'✓' if reddit_ok else '○ bloqueia $'}</span></div>
    </div>

    <div class="section-label">Carteira</div>
    <div class="sg sg2">
        <div class="st"><span class="sl">Wallet</span><span class="sv" style="font-size:11px">{wallet or 'Não configurada'}</span></div>
        <div class="st"><span class="sl">FluxA</span><span class="sv" style="font-size:11px">{fluxa or 'Não configurado'}</span></div>
    </div>
</div>"""

    logs_html = "".join(f"<li>{l}</li>" for l in CACHE["logs"][-12:])

    def block_str(items, name):
        if not items:
            return ""
        return f"""<div class="block-item">{name}<span class="badge {'err' if items else 'online'}">{len(items)}</span></div><div style="font-size:11px;color:#f87171">{', '.join(items[:-1]) + ' e ' + items[-1] if len(items) > 1 else items[0]} bloqueando ganhos</div>"""

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
.sum {{ display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; }}
.sc {{ background:#1e293b; border-radius:10px; padding:10px 16px; flex:1; min-width:120px; border:1px solid #334155; }}
.sc .l {{ color:#94a3b8; font-size:10px; }}
.sc .v {{ font-size:20px; font-weight:700; color:#22c55e; }}
.sc .v.xp {{ color:#a78bfa; }}
.sc .v.yl {{ color:#f59e0b; }}
.sc .v.rd {{ color:#f87171; }}
.blocker {{ background:#1e293b; border-radius:10px; padding:12px 16px; margin-bottom:16px; border:1px solid #ef4444; }}
.blocker h3 {{ font-size:13px; color:#fca5a5; margin-bottom:6px; }}
.block-item {{ display:flex; align-items:center; gap:8px; font-size:12px; margin-bottom:4px; }}
.badge {{ font-size:10px; padding:2px 7px; border-radius:8px; font-weight:600; }}
.badge.err {{ background:#7f1d1d; color:#fca5a5; }}
.badge.online {{ background:#166534; color:#86efac; }}
.badge.alli {{ background:#7c3aed; color:#ddd6fe; }}
.badge.lvl {{ background:#1e40af; color:#bfdbfe; }}
.badge.paused-badge {{ background:#92400e; color:#fde68a; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:10px; }}
.card {{ background:#1e293b; border-radius:10px; padding:12px; border:1px solid #334155; }}
.card.error {{ border-color:#ef4444; }}
.card.paused {{ border-color:#f59e0b; opacity:0.7; }}
.ch {{ display:flex; align-items:center; gap:6px; margin-bottom:8px; flex-wrap:wrap; }}
.cn {{ font-size:14px; font-weight:600; }}
.er {{ color:#fca5a5; font-size:12px; }}
.api-err {{ background:#7f1d1d; color:#fca5a5; font-size:10px; padding:3px 6px; border-radius:4px; margin-bottom:4px; font-family:monospace; }}
.section-label {{ font-size:10px; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin:8px 0 3px; }}
.sg {{ display:grid; gap:3px; }}
.sg2 {{ grid-template-columns:repeat(2,1fr); }}
.sg4 {{ grid-template-columns:repeat(4,1fr); }}
.sg5 {{ grid-template-columns:repeat(5,1fr); }}
.st {{ text-align:center; padding:4px 2px; background:#0f172a; border-radius:5px; }}
.st.gr {{ background:#064e3b; }}
.st.na {{ }}
.st.rd {{ background:#7f1d1d; }}
.sl {{ display:block; color:#94a3b8; font-size:9px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.sv {{ font-size:12px; font-weight:600; }}
.sv.gr {{ color:#22c55e; }}
.sv.yl {{ color:#f59e0b; }}
.sv.pu {{ color:#a78bfa; }}
.sv.rd {{ color:#f87171; }}
.dq-grid {{ display:flex; flex-wrap:wrap; gap:3px; }}
.dq-item {{ display:flex; align-items:center; gap:4px; background:#0f172a; padding:3px 7px; border-radius:5px; font-size:10px; }}
.dq-item.done {{ background:#166534; }}
.dq-name {{ flex:1; }}
.dq-status {{ font-weight:700; color:#22c55e; }}
.logs {{ background:#1e293b; border-radius:10px; padding:12px; margin-top:14px; border:1px solid #334155; }}
.logs h2 {{ font-size:12px; margin-bottom:6px; }}
.logs ul {{ list-style:none; font-family:monospace; font-size:10px; color:#94a3b8; }}
.logs li {{ padding:1px 0; }}
.ft {{ text-align:center; color:#475569; font-size:10px; margin-top:14px; }}
</style>
<meta http-equiv="refresh" content="15">
</head>
<body>
<h1>Aurum Dashboard</h1>
<p class="sub">{len(AGENTS)} bots • Refresh 15s • {CACHE['last_update'] or '...'}</p>

{f'''<div class="blocker"><h3>O que está bloqueando ganhos</h3>{''.join(f'<div class="block-item">• {a}</div>' for a in actions_global)}</div>''' if actions_global else ''}

<div class="sum">
    <div class="sc"><div class="l">USDC Total</div><div class="v">${totals['usdc']:.4f}</div></div>
    <div class="sc"><div class="l">XP Total</div><div class="v xp">{totals['xp']}</div></div>
    <div class="sc"><div class="l">Quest Wins</div><div class="v">{totals['wins']}</div></div>
    <div class="sc"><div class="l">Streak Média</div><div class="v yl">{totals['streak']/len(AGENTS):.1f}d</div></div>
    <div class="sc"><div class="l">Redes Sociais</div><div class="v {'rd' if totals['discord'] < len(AGENTS) else 'gr'}">{totals['email']}/{totals['discord']}/{totals['twitter']}/{totals['reddit']} ✓</div></div>
    <div class="sc"><div class="l">Daily Quests</div><div class="v yl">{totals['daily_done']}/15</div></div>
</div>
<div class="grid">{cards}</div>
<div class="logs">
    <h2>Atividade</h2>
    <ul>{logs_html}</ul>
</div>
<div class="ft">AgentHansa • Dados via API • Atualiza a cada 30s</div>
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
print(f"  Aurum Dashboard")
print(f"  http://localhost:5000")
print(f"{'='*40}\n")
HTTPServer(("0.0.0.0", 5000), Handler).serve_forever()
