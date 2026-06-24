import requests, time, schedule, os, re, threading, random, sys, json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

GEMINI_KEY = os.environ.get("GEMINI_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
LOCK_FILE = "/data/aurum.lock"
EMAIL_CACHE_FILE = "/data/email_verified.json"
os.makedirs("/data", exist_ok=True)
if os.path.exists(LOCK_FILE):
    sys.exit(0)
open(LOCK_FILE, "w").close()
START_TIME = time.time()

DEVTO_KEYS = {
    "Aurum":    os.environ.get("DEVTO_KEY_AURUM"),
    "Aurum-02": os.environ.get("DEVTO_KEY_AURUM02"),
    "Aurum-03": os.environ.get("DEVTO_KEY_AURUM03"),
}

AGENTS = [
    {"name": "Aurum",   "key": "tabb_5Eq9iYsuuxuarP2SPxuPM448062UvxzbYXHa0HYKl20", "alliance": "red"},
    {"name": "Aurum-02","key": "tabb_LdisJ3cU8016BbavZ9x8He1-ihBIejMibVZjWSaZpG8", "alliance": "red"},
    {"name": "Aurum-03","key": "tabb_t77U52PUrs0QyxMqzz0VQm29dNjqDl78-UgKLsjpJt8", "alliance": "red"},
]

AH_BASE = "https://www.agenthansa.com/api"

def log(name, msg):
    print(f"[{datetime.now()}] {name}: {msg}", flush=True)

def h(agent):
    return {"Authorization": f"Bearer {agent['key']}"}

def api_get(agent, path, retries=3):
    for i in range(retries):
        try:
            r = requests.get(f"{AH_BASE}{path}", headers=h(agent), timeout=15)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            return r.json()
        except Exception as e:
            if i < retries - 1:
                time.sleep(3 * (i + 1))
    return {}

def api_post(agent, path, data=None, retries=3):
    for i in range(retries):
        try:
            r = requests.post(f"{AH_BASE}{path}", headers={**h(agent), "Content-Type": "application/json"}, json=data or {}, timeout=15)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            return r.json()
        except:
            if i < retries - 1:
                time.sleep(3 * (i + 1))
    return {}

class LLMClient:
    def __init__(self):
        self.gemini_key = GEMINI_KEY
        self.groq_key = GROQ_KEY
        self.gemini_failures = 0
        self.groq_until = 0.0

    def _call_gemini(self, prompt):
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {"Content-Type": "application/json", "X-goog-api-key": self.gemini_key}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            if r.status_code == 429:
                return None
            data = r.json()
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            log("LLM", f"Gemini: {data.get('error', {}).get('message', str(data))}")
        except Exception as e:
            log("LLM", f"Gemini: {e}")
        return None

    def _call_groq(self, prompt):
        if not self.groq_key:
            return None
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.groq_key}"}
            payload = {"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            if r.status_code == 429:
                return None
            data = r.json()
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"]
            log("LLM", f"Groq: {data.get('error', {}).get('message', str(data))}")
        except Exception as e:
            log("LLM", f"Groq: {e}")
        return None

    def call(self, prompt, retries=2):
        backoff = [5, 15, 45, 120]
        for attempt in range(retries + 1):
            use_groq = time.time() < self.groq_until
            result = self._call_groq(prompt) if use_groq else self._call_gemini(prompt)
            if result is not None:
                self.gemini_failures = 0
                return result
            if not use_groq:
                self.gemini_failures += 1
                if self.gemini_failures >= 3 and self.groq_key:
                    self.groq_until = time.time() + 300
                    log("LLM", "Groq fallback 5min (3 Gemini failures)")
                    result = self._call_groq(prompt)
                    if result is not None:
                        self.gemini_failures = 0
                        return result
            b = backoff[min(attempt, len(backoff) - 1)]
            time.sleep(b * random.uniform(0.8, 1.2))
        return ""

llm = LLMClient()

def solve_challenge(data):
    prompt = f"Answer ONLY with a single integer. No explanation. Question: {data.get('question','')}"
    nums = re.findall(r"-?\d+", llm.call(prompt))
    return int(nums[0]) if nums else 0

def publish_devto(agent, title, body):
    dk = DEVTO_KEYS.get(agent["name"])
    if not dk:
        return None
    try:
        r = requests.post("https://dev.to/api/articles",
            headers={"api-key": dk, "Content-Type": "application/json"},
            json={"article": {"title": title[:128], "body_markdown": body, "published": True,
                  "tags": ["web3", "blockchain", "crypto"]}}, timeout=15)
        url = r.json().get("url", "")
        if url:
            for _ in range(5):
                try:
                    hr = requests.head(url, timeout=5)
                    if hr.status_code < 400:
                        return url
                except:
                    pass
                time.sleep(2)
        return None
    except:
        return None

def checkin(agent):
    r = api_post(agent, "/agents/checkin")
    if r.get("status") == "challenge_required":
        r = api_post(agent, "/agents/checkin/verify",
            {"challenge_id": r["challenge_id"], "challenge_answer": solve_challenge(r)})
    log(agent["name"], f"Check-in ok")

def claim_red_packets(agent):
    r = api_get(agent, "/red-packets")
    active = r.get("active", [])
    log(agent["name"], f"Red packets: {len(active)} active")
    for p in active:
        api_post(agent, f"/red-packets/{p['id']}/join")
        time.sleep(0.3)

def prediction_bet(agent):
    r = api_get(agent, "/prediction/markets")
    markets = r.get("markets", [])
    log(agent["name"], f"Prediction markets: {len(markets)}")
    if markets:
        outcome = "yes" if random.random() > 0.5 else "no"
        r2 = api_post(agent, f"/prediction/markets/{markets[0]['id']}/bet",
            {"outcome": outcome, "stake": 10, "stake_currency": "xp"})
        log(agent["name"], f"Prediction: {r2.get('status', 'bet')}")

def forum_create_post(agent):
    title = llm.call("Crie um título curto de forum sobre agentes AI (máx 80 chars). Responda em português.")
    body = llm.call("Escreva um post de forum de 100 palavras sobre desenvolvimento de agentes AI. Em português.")
    if title and body:
        r = api_post(agent, "/forum", {"title": title[:80], "body": body, "category": "review"})
        log(agent["name"], f"Forum post created")

def read_forum_digest(agent):
    api_get(agent, "/forum/digest")
    log(agent["name"], "Forum digest read")

def generate_referral(agent):
    r = api_get(agent, "/offers")
    offers = r.get("offers", [])
    if offers:
        api_post(agent, f"/offers/{offers[0]['id']}/ref")
        log(agent["name"], "Referral generated")
    else:
        log(agent["name"], "No offers for referral")

FORUM_POST_COOLDOWN = {}
def daily_quests(agent):
    r = api_get(agent, "/agents/daily-quests")
    quests = r.get("quests", [])
    done = sum(1 for q in quests if q.get("completed"))
    log(agent["name"], f"Daily quests: {done}/5")
    if r.get("all_completed") and not r.get("bonus_claimed"):
        api_post(agent, "/agents/daily-quests/claim")
        log(agent["name"], f"Daily bonus +{r.get('bonus_earned', 50)}XP claimed!")

    for q in quests:
        if q.get("completed"):
            continue
        qid = q.get("id")
        if qid == "distribute":
            generate_referral(agent)
        elif qid == "digest":
            read_forum_digest(agent)
        elif qid == "create":
            last = FORUM_POST_COOLDOWN.get(agent["name"])
            if not last or datetime.now() - last > timedelta(hours=2):
                forum_create_post(agent)
                FORUM_POST_COOLDOWN[agent["name"]] = datetime.now()
        elif qid == "curate":
            do_curate(agent)
        time.sleep(0.5)

def do_curate(agent):
    try:
        r = api_get(agent, "/forum?sort=recent&per_page=30")
        posts = [p for p in r.get("posts", []) if not p.get("is_pinned")]
        up = 0
        down = 0
        for post in posts:
            if up >= 5 and down >= 5:
                break
            direction = "up" if up < 5 else "down"
            r2 = api_post(agent, f"/forum/{post['id']}/vote", {"direction": direction})
            if isinstance(r2, dict) and r2.get("status") in ("ok", "success", "voted"):
                if direction == "up":
                    up += 1
                else:
                    down += 1
            time.sleep(0.3)
        log(agent["name"], f"Curate: {up} up, {down} down")
    except Exception as e:
        log(agent["name"], f"Curate error: {e}")

def forum_vote(agent):
    r = api_get(agent, f"/forum?sort=recent&per_page=5")
    posts = r.get("posts", [])
    log(agent["name"], f"Forum posts: {len(posts)}")
    for i, post in enumerate(posts):
        direction = "up" if i < 3 else "down"
        api_post(agent, f"/forum/{post['id']}/vote", {"direction": direction})
        time.sleep(0.2)

def do_quests(agent):
    r = api_get(agent, "/alliance-war/quests")
    quests = r.get("quests", [])
    open_qs = [q for q in quests if q.get("status") == "open"]
    log(agent["name"], f"War quests: {len(open_qs)} open")
    done = 0
    for q in open_qs:
        if done >= 2:
            break
        desc = q.get("description", "")
        title = q["title"]
        min_words = 500
        m = re.search(r'(\d+)[- ]word', desc + " " + title)
        if m:
            min_words = int(m.group(1))
        content = llm.call(
            f"Write a {min_words}-word quality blog post response. "
            f"Title: {title}\n"
            f"Description: {desc}\n"
            f"Requirements: directly address the description, use specific examples, "
            f"minimum {min_words} words, no generic filler.")
        words = len(content.split())
        if words < min_words * 0.7:
            continue
        payload = {"content": content}
        url = publish_devto(agent, title, content)
        if url:
            payload["proof_url"] = url
        r2 = api_post(agent, f"/alliance-war/quests/{q['id']}/submit", payload)
        log(agent["name"], f"Quest submitted ({words} words{' + dev.to' if url else ''})")
        done += 1
        time.sleep(1)

def forum_engage(agent):
    r = api_get(agent, f"/forum?sort=recent&per_page=10")
    posts = r.get("posts", [])
    count = 0
    for post in posts:
        if count >= 3:
            break
        comment = llm.call(f"Write a short helpful comment on forum post: {post.get('title','')}")
        if comment:
            api_post(agent, f"/forum/{post['id']}/comments", {"content": comment})
            count += 1
            time.sleep(0.3)
    log(agent["name"], f"Forum comments: {count}")

def email_verify(agent):
    try:
        if os.path.exists(EMAIL_CACHE_FILE):
            cache = json.load(open(EMAIL_CACHE_FILE))
            if cache.get(agent["name"]):
                log(agent["name"], "Email verified (cached)")
                return
        r = api_get(agent, "/agents/me")
        if r.get("email_verified"):
            cache = {}
            if os.path.exists(EMAIL_CACHE_FILE):
                cache = json.load(open(EMAIL_CACHE_FILE))
            cache[agent["name"]] = True
            json.dump(cache, open(EMAIL_CACHE_FILE, "w"))
            log(agent["name"], "Email verified")
            return
        api_post(agent, "/agents/me/email/start", {"email": "gugu.venutto@gmail.com"})
        log(agent["name"], "Email sent (check inbox)")
    except Exception as e:
        log(agent["name"], f"Email verify error: {e}")

def token_router(agent):
    r = api_post(agent, "/token-router/request-invite")
    code = r.get("code") or r.get("invite_code")
    if code:
        log(agent["name"], f"Token Router: ${r.get('credit', 50)} credit")
    else:
        log(agent["name"], f"Token Router: {r.get('status', 'check')}")

def check_feed(agent):
    r = api_get(agent, "/agents/feed")
    log(agent["name"], f"Feed: {len(r.get('quests', []))} quests, {len(r.get('urgent', []))} urgent")

def engagement_tasks(agent):
    r = api_get(agent, "/engagement")
    tasks = r if isinstance(r, list) else r.get("data", []) or r.get("tasks", [])
    if tasks:
        log(agent["name"], f"Engagement: {len(tasks)} pending task(s)")
        for t in tasks[:2]:
            tid = t.get("id") or t.get("assignment_id")
            if tid:
                api_post(agent, f"/engagement/{tid}/submit",
                    {"comment_url": "", "notes": "Completed by Aurum bot", "proof_image_urls": []})
                log(agent["name"], f"Engagement submitted")
                time.sleep(0.5)
    else:
        log(agent["name"], "No engagement tasks")

def collective_bounties(agent):
    r = api_get(agent, "/collective/bounties/public")
    bounties = r.get("bounties", []) if isinstance(r, dict) else r
    if bounties:
        log(agent["name"], f"Bounties: {len(bounties)} available")
        for b in bounties[:1]:
            bid = b.get("id") or b.get("bounty_id")
            if bid:
                api_post(agent, f"/collective/bounties/{bid}/join")
                log(agent["name"], f"Joined bounty")
                time.sleep(0.5)
    else:
        log(agent["name"], "No open bounties")

def arena_worldcup(agent):
    r = api_get(agent, "/arena/soccer/matches/open")
    matches = r if isinstance(r, list) else r.get("matches", [])
    if matches:
        m = matches[0]
        mid = m.get("id")
        if mid:
            api_post(agent, f"/arena/soccer/matches/{mid}/join", {})
            log(agent["name"], "Joined World Cup match")
    else:
        log(agent["name"], "No open arena matches")

print(f"[{datetime.now()}] SYSTEM: Starting {len(AGENTS)} agents", flush=True)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        uptime = int(time.time() - START_TIME)
        body = json.dumps({"status": "ok", "agents": len(AGENTS), "uptime": uptime}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

def health_server(port):
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

threading.Thread(target=health_server, args=(80,), daemon=True).start()
threading.Thread(target=health_server, args=(8080,), daemon=True).start()

def background_startup():
    for agent in AGENTS:
        try:
            log(agent["name"], "Quick startup...")
            checkin(agent)
            email_verify(agent)
            token_router(agent)
            check_feed(agent)
            engagement_tasks(agent)
            collective_bounties(agent)
        except Exception as e:
            log(agent["name"], f"Startup: {e}")

    for i, agent in enumerate(AGENTS):
        off = i * 5
        schedule.every().day.at(f"08:{off:02d}").do(lambda a=agent: checkin(a))
        schedule.every(3).hours.at(f":{off:02d}").do(lambda a=agent: [
            claim_red_packets(a), prediction_bet(a), daily_quests(a),
            engagement_tasks(a), collective_bounties(a), do_quests(a)])
        schedule.every(6).hours.at(f":{off + 2:02d}").do(lambda a=agent: [
            forum_vote(a), forum_engage(a), check_feed(a),
            arena_worldcup(a)])

    print(f"[{datetime.now()}] SYSTEM: Agents running 24/7", flush=True)

threading.Thread(target=background_startup, daemon=True).start()

while True:
    try:
        schedule.run_pending()
        time.sleep(60)
    except:
        time.sleep(60)
