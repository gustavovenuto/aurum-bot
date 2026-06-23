import requests, time, schedule, os, re, threading, random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

GEMINI_KEY = os.environ.get("GEMINI_KEY")

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

def call_llm(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                  {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                  {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                  {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                time.sleep(10)
                continue
            data = r.json()
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            time.sleep(5)
        except:
            time.sleep(5)
    return ""

def solve_challenge(data):
    prompt = f"Answer ONLY with a single integer. No explanation. Question: {data.get('question','')}"
    nums = re.findall(r"-?\d+", call_llm(prompt))
    return int(nums[0]) if nums else 0

def publish_devto(agent, title, body):
    dk = DEVTO_KEYS.get(agent["name"])
    if not dk:
        return None
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:50]
    try:
        r = requests.post("https://dev.to/api/articles",
            headers={"api-key": dk, "Content-Type": "application/json"},
            json={"article": {
                "title": title[:128],
                "body_markdown": body,
                "published": True,
                "tags": ["web3", "blockchain", "crypto"],
                "canonical_url": f"https://dev.to/{slug}"
            }}, timeout=15)
        url = r.json().get("url", "")
        if url:
            log(agent["name"], f"dev.to: {url}")
        return url
    except Exception as e:
        log(agent["name"], f"dev.to error: {e}")
    return None

def checkin(agent):
    r = requests.post(f"{AH_BASE}/agents/checkin", headers=h(agent))
    data = r.json()
    if data.get("status") == "challenge_required":
        r = requests.post(f"{AH_BASE}/agents/checkin/verify", headers=h(agent),
            json={"challenge_id": data["challenge_id"], "challenge_answer": solve_challenge(data)})
        data = r.json()
    log(agent["name"], f"Check-in: {data.get('points_earned', 'ok')}pts")

def claim_red_packets(agent):
    try:
        packets = requests.get(f"{AH_BASE}/red-packets", headers=h(agent), timeout=10).json()
        for p in packets.get("data", []):
            if p.get("status") == "active":
                r = requests.post(f"{AH_BASE}/red-packets/{p['id']}/join", headers=h(agent))
                log(agent["name"], f"Red packet: {r.json().get('amount', 'claimed')}")
                time.sleep(0.3)
    except Exception as e:
        log(agent["name"], f"Red packet error: {e}")

def prediction_bet(agent):
    try:
        r = requests.get(f"{AH_BASE}/prediction/markets", headers=h(agent), timeout=10)
        markets = r.json().get("data", [])
        if not markets:
            return
        m = markets[0]
        r2 = requests.post(f"{AH_BASE}/prediction/markets/{m['id']}/bet", headers=h(agent),
            json={"outcome": "yes", "stake": 0.50, "stake_currency": "usdc"})
        log(agent["name"], f"Prediction: {r2.json().get('status', 'bet')}")
    except Exception as e:
        log(agent["name"], f"Prediction error: {e}")

def daily_quests(agent):
    try:
        r = requests.get(f"{AH_BASE}/agents/daily-quests", headers=h(agent), timeout=10)
        quests = r.json().get("data", [])
        for q in quests:
            content = call_llm(f"Quick answer for: {q.get('title','')}")
            if content:
                requests.post(f"{AH_BASE}/side-quests/submit", headers=h(agent),
                    json={"quest_id": q.get("id"), "content": content})
                time.sleep(0.3)
        log(agent["name"], f"Daily quests: {len(quests)} done")
    except Exception as e:
        log(agent["name"], f"Daily quests error: {e}")

def forum_vote(agent):
    try:
        posts = requests.get(f"{AH_BASE}/forum", headers=h(agent), timeout=10).json()
        for post in posts.get("data", [])[:5]:
            requests.post(f"{AH_BASE}/forum/{post.get('id')}/vote", headers=h(agent),
                json={"direction": "up"})
            time.sleep(0.2)
        log(agent["name"], "Forum votes done")
    except Exception as e:
        log(agent["name"], f"Vote error: {e}")

def do_quests(agent):
    try:
        quests = requests.get(f"{AH_BASE}/alliance-war/quests", headers=h(agent), timeout=10).json()
        done = 0
        for q in quests.get("data", []):
            if q.get("status") == "open" and done < 2:
                content = call_llm(
                    f"Write a 500-word quality response. Title: {q['title']}\nDescription: {q.get('description', '')}"
                )
                words = len(content.split())
                if words < 350:
                    continue
                payload = {"content": content}
                url = publish_devto(agent, q['title'], content)
                if url:
                    payload["proof_url"] = url
                r = requests.post(f"{AH_BASE}/alliance-war/quests/{q['id']}/submit",
                    headers={**h(agent), "Content-Type": "application/json"},
                    json=payload)
                log(agent["name"], f"Quest: {r.json().get('status', 'submitted')} ({words} words{' + dev.to' if url else ''})")
                requests.post(f"{AH_BASE}/alliance-war/quests/{q['id']}/verify", headers=h(agent))
                done += 1
                time.sleep(1)
    except Exception as e:
        log(agent["name"], f"Quest error: {e}")

def forum_engage(agent):
    try:
        posts = requests.get(f"{AH_BASE}/forum", headers=h(agent), timeout=10).json()
        count = 0
        for post in posts.get("data", []):
            if count >= 3:
                break
            comment = call_llm(
                f"Write a helpful 80-word comment on forum post: {post.get('title','')}"
            )
            if comment:
                requests.post(f"{AH_BASE}/forum/{post['id']}/comment",
                    headers=h(agent), json={"content": comment})
                count += 1
                time.sleep(0.3)
    except Exception as e:
        log(agent["name"], f"Forum error: {e}")

def email_verify(agent):
    try:
        r = requests.get(f"{AH_BASE}/agents/me/email/status", headers=h(agent), timeout=10)
        if not r.json().get("verified"):
            requests.post(f"{AH_BASE}/agents/me/email/start", headers=h(agent),
                json={"email": "gugu.venutto@gmail.com"})
            log(agent["name"], "Email verification sent (check inbox and click link)")
    except:
        pass

def run_agent_tasks(agent):
    checkin(agent)
    time.sleep(random.uniform(1, 3))
    claim_red_packets(agent)
    time.sleep(random.uniform(1, 3))
    prediction_bet(agent)
    time.sleep(random.uniform(1, 3))
    daily_quests(agent)
    time.sleep(random.uniform(1, 3))
    do_quests(agent)
    time.sleep(random.uniform(1, 3))
    forum_vote(agent)
    time.sleep(random.uniform(1, 3))
    forum_engage(agent)

log("SYSTEM", f"Starting {len(AGENTS)} agents")

for agent in AGENTS:
    try:
        log(agent["name"], "Running initial tasks...")
        run_agent_tasks(agent)
        email_verify(agent)
    except Exception as e:
        log(agent["name"], f"Initial error: {e}")

for agent in AGENTS:
    i = AGENTS.index(agent)
    offset = i * 5
    schedule.every().day.at(f"08:{offset:02d}").do(lambda a=agent: checkin(a))
    schedule.every(3).hours.at(f":{offset:02d}").do(lambda a=agent: claim_red_packets(a))
    schedule.every(4).hours.at(f":{offset:02d}").do(lambda a=agent: [prediction_bet(a), daily_quests(a)])
    schedule.every(6).hours.at(f":{offset:02d}").do(lambda a=agent: [do_quests(a), forum_vote(a), forum_engage(a)])

def health_server():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *a):
            pass
    HTTPServer(("0.0.0.0", 8080), H).serve_forever()

threading.Thread(target=health_server, daemon=True).start()
log("SYSTEM", "Agents running 24/7")

while True:
    try:
        schedule.run_pending()
        time.sleep(60)
    except:
        time.sleep(60)
