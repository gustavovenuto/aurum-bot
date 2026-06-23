import requests, time, schedule, os, re, threading, random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

GEMINI_KEY = os.environ.get("GEMINI_KEY")

AGENTS = [
    {"name": "Aurum",   "key": "tabb_5Eq9iYsuuxuarP2SPxuPM448062UvxzbYXHa0HYKl20", "alliance": "red"},
    {"name": "Aurum-02","key": "tabb_LdisJ3cU8016BbavZ9x8He1-ihBIejMibVZjWSaZpG8", "alliance": "red"},
    {"name": "Aurum-03","key": "tabb_t77U52PUrs0QyxMqzz0VQm29dNjqDl78-UgKLsjpJt8", "alliance": "red"},
]

AH_BASE = "https://www.agenthansa.com/api"

def log(name, msg):
    print(f"[{datetime.now()}] {name}: {msg}", flush=True)

def call_llm(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                time.sleep(10)
                continue
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            log("LLM", f"error: {e}")
            time.sleep(5)
    return ""

def solve_challenge(data):
    q = data.get("question", "")
    prompt = f"Answer ONLY with a single integer. No explanation. Question: {q}"
    ans = call_llm(prompt)
    nums = re.findall(r"-?\d+", ans)
    return int(nums[0]) if nums else 0

def checkin(agent):
    h = {"Authorization": f"Bearer {agent['key']}"}
    r = requests.post(f"{AH_BASE}/agents/checkin", headers=h)
    data = r.json()
    if data.get("status") == "challenge_required":
        ans = solve_challenge(data)
        r = requests.post(f"{AH_BASE}/agents/checkin/verify", headers=h,
            json={"challenge_id": data["challenge_id"], "challenge_answer": ans})
        data = r.json()
    log(agent["name"], f"Check-in: {data.get('points_earned', 'ok')}pts")

def claim_red_packets(agent):
    h = {"Authorization": f"Bearer {agent['key']}"}
    try:
        packets = requests.get(f"{AH_BASE}/red-packets", headers=h, timeout=10).json()
        for p in packets.get("data", []):
            if p.get("status") == "active":
                r = requests.post(f"{AH_BASE}/red-packets/{p['id']}/join", headers=h)
                log(agent["name"], f"Red packet: {r.json().get('amount', 'claimed')}")
                time.sleep(0.3)
    except Exception as e:
        log(agent["name"], f"Red packet error: {e}")

def do_quests(agent):
    h = {"Authorization": f"Bearer {agent['key']}"}
    try:
        quests = requests.get(f"{AH_BASE}/alliance-war/quests", headers=h, timeout=10).json()
        done = 0
        for q in quests.get("data", []):
            if q.get("status") == "open" and done < 2:
                content = call_llm(
                    f"Write a 400-word quality response. Title: {q['title']}\nDescription: {q.get('description', '')}"
                )
                if not content:
                    continue
                r = requests.post(f"{AH_BASE}/alliance-war/quests/{q['id']}/submit",
                    headers={**h, "Content-Type": "application/json"},
                    json={"content": content})
                log(agent["name"], f"Quest: {r.json().get('status', 'submitted')}")
                requests.post(f"{AH_BASE}/alliance-war/quests/{q['id']}/verify", headers=h)
                done += 1
                time.sleep(1)
    except Exception as e:
        log(agent["name"], f"Quest error: {e}")

def forum_engage(agent):
    h = {"Authorization": f"Bearer {agent['key']}"}
    try:
        posts = requests.get(f"{AH_BASE}/forum", headers=h, timeout=10).json()
        count = 0
        for post in posts.get("data", []):
            if count >= 3:
                break
            comment = call_llm(
                f"Write a helpful 80-word comment on forum post: {post.get('title','')}"
            )
            if comment:
                requests.post(f"{AH_BASE}/forum/{post['id']}/comment",
                    headers=h, json={"content": comment})
                count += 1
                time.sleep(0.3)
    except Exception as e:
        log(agent["name"], f"Forum error: {e}")

def run_agent_tasks(agent):
    checkin(agent)
    time.sleep(random.uniform(1, 5))
    claim_red_packets(agent)
    time.sleep(random.uniform(1, 5))
    do_quests(agent)
    time.sleep(random.uniform(1, 5))
    forum_engage(agent)

log("SYSTEM", f"Starting {len(AGENTS)} agents") 

for agent in AGENTS:
    try:
        log(agent["name"], "Running initial tasks...")
        run_agent_tasks(agent)
    except Exception as e:
        log(agent["name"], f"Initial error: {e}")

for agent in AGENTS:
    i = AGENTS.index(agent)
    offset = i * 5
    schedule.every().day.at(f"08:{offset:02d}").do(lambda a=agent: checkin(a))
    schedule.every(3).hours.at(f":{offset:02d}").do(lambda a=agent: claim_red_packets(a))
    schedule.every(4).hours.at(f":{offset:02d}").do(lambda a=agent: do_quests(a))
    schedule.every(6).hours.at(f":{offset:02d}").do(lambda a=agent: forum_engage(a))

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
    except Exception as e:
        log("SYSTEM", f"Loop: {e}")
        time.sleep(60)
