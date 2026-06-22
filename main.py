import requests, time, schedule, os, json, sys, re, threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

AH_API_KEY = os.environ.get("AH_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
AH_BASE = "https://www.agenthansa.com/api"
AH_HEADERS = {"Authorization": f"Bearer {AH_API_KEY}"}

def log(msg):
    print(f"[{datetime.now()}] {msg}", flush=True)

def call_llm(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                log(f"Rate limited, waiting 30s...")
                time.sleep(30)
                continue
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            log(f"LLM error: {e}, retry {attempt+1}")
            time.sleep(5)
    return ""

def solve_challenge(data):
    q = data.get("question", "")
    log(f"Challenge: {q}")
    prompt = f"Answer ONLY with a single integer. No explanation. Question: {q}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 429:
                time.sleep(5)
                continue
            nums = re.findall(r'-?\d+', r.json()["candidates"][0]["content"]["parts"][0]["text"])
            if nums:
                return int(nums[0])
        except:
            time.sleep(3)
    return 0

def checkin():
    r = requests.post(f"{AH_BASE}/agents/checkin", headers=AH_HEADERS)
    data = r.json()
    if data.get("status") == "challenge_required":
        cid = data["challenge_id"]
        ans = solve_challenge(data)
        r2 = requests.post(f"{AH_BASE}/agents/checkin/verify", headers=AH_HEADERS, json={"challenge_id": cid, "challenge_answer": ans})
        data = r2.json()
    log(f"Check-in: {data}")

def claim_red_packets():
    try:
        packets = requests.get(f"{AH_BASE}/red-packets", headers=AH_HEADERS, timeout=10).json()
        for p in packets.get("data", []):
            if p.get("status") == "active":
                r = requests.post(f"{AH_BASE}/red-packets/{p['id']}/join", headers=AH_HEADERS)
                log(f"Red packet {p['id']}: {r.json()}")
                time.sleep(0.5)
    except Exception as e:
        log(f"Red packet error: {e}")

def do_quests():
    try:
        quests = requests.get(f"{AH_BASE}/alliance-war/quests", headers=AH_HEADERS, timeout=10).json()
        done = 0
        for q in quests.get("data", []):
            if q.get("status") == "open" and done < 3:
                content = call_llm(
                    f"Write a 500-word quality response for this quest. "
                    f"Title: {q['title']}\nDescription: {q.get('description', '')}"
                )
                if not content:
                    continue
                r = requests.post(
                    f"{AH_BASE}/alliance-war/quests/{q['id']}/submit",
                    headers={**AH_HEADERS, "Content-Type": "application/json"},
                    json={"content": content}
                )
                log(f"Quest {q['id']}: {r.json()}")
                requests.post(f"{AH_BASE}/alliance-war/quests/{q['id']}/verify", headers=AH_HEADERS)
                done += 1
                time.sleep(2)
    except Exception as e:
        log(f"Quest error: {e}")

def forum_engage():
    try:
        posts = requests.get(f"{AH_BASE}/forum", headers=AH_HEADERS, timeout=10).json()
        count = 0
        for post in posts.get("data", []):
            if count >= 4:
                break
            comment = call_llm(
                f"Write a helpful 100-word comment on this forum post: {post.get('title','')}"
            )
            if comment:
                requests.post(
                    f"{AH_BASE}/forum/{post['id']}/comment",
                    headers=AH_HEADERS,
                    json={"content": comment}
                )
                count += 1
                time.sleep(0.3)
    except Exception as e:
        log(f"Forum error: {e}")

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
log("Agent started - running initial tasks")

for fn in [checkin, claim_red_packets, do_quests, forum_engage]:
    try:
        fn()
        time.sleep(2)
    except Exception as e:
        log(f"Initial task error: {e}")

log("Initial tasks done, entering schedule loop")

schedule.every().day.at("08:00").do(checkin)
schedule.every(3).hours.do(claim_red_packets)
schedule.every(4).hours.do(do_quests)
schedule.every(6).hours.do(forum_engage)

while True:
    try:
        schedule.run_pending()
        time.sleep(60)
    except Exception as e:
        log(f"Loop error: {e}")
        time.sleep(60)
