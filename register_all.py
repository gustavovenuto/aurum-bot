import requests, re, time, sys, json, os

GEMINI_KEY = os.environ.get("GEMINI_KEY")
results = {}

for i in range(2, 21):
    name = f"Aurum-{i:02d}"
    print(f"\n[{i}/20] {name}...", end=" ", flush=True)
    
    r = requests.post("https://www.agenthansa.com/api/agents/register",
        json={"name": name, "description": f"AI agent #{i}"}, timeout=15)
    data = r.json()
    
    if "api_key" in data:
        key = data["api_key"]
        print(f"KEY: {key[:20]}...")
    elif data.get("status") == "challenge_required":
        prompt = f"Answer ONLY integer. Question: {data['question']}"
        r2 = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        ans = re.findall(r"-?\d+", r2.json()["candidates"][0]["content"]["parts"][0]["text"])[0]
        r3 = requests.post("https://www.agenthansa.com/api/agents/register/verify",
            json={"challenge_id": data["challenge_id"], "challenge_answer": int(ans)}, timeout=15)
        d3 = r3.json()
        if "api_key" in d3:
            key = d3["api_key"]
            print(f"KEY: {key[:20]}...")
        else:
            print(f"FAIL: {d3.get('detail', d3)}")
            time.sleep(10)
            continue
    else:
        print(f"SKIP: {data.get('detail', data)}")
        time.sleep(10)
        continue
    
    a = "red" if i <= 7 else "blue" if i <= 14 else "green"
    requests.patch("https://www.agenthansa.com/api/agents/alliance",
        headers={"Authorization": f"Bearer {key}"}, json={"alliance": a}, timeout=10)
    print(f"  -> {a.upper()}")
    results[name] = key
    
    if i < 20:
        print("  waiting 60s...")
        time.sleep(60)

print("\n\n=== ALL KEYS ===")
for n, k in results.items():
    print(f"{n}:{k}")
