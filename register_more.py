import requests, re, time, os

GEMINI_KEY = os.environ.get("GEMINI_KEY")
results = {}
quota = {"used": 0, "max": 1500}

for i in range(1, 21):
    name = f"Aurum-{i:02d}"
    print(f"\n[{i}/20] {name}...", end=" ", flush=True)
    
    r = requests.post("https://www.agenthansa.com/api/agents/register",
        json={"name": name, "description": f"AI agent #{i}"})
    data = r.json()
    
    if "api_key" in data:
        key = data["api_key"]
        print(f"OK: {key[:20]}...")
    elif data.get("status") == "challenge_required":
        prompt = f"Answer ONLY integer. Question: {data['question']}"
        r2 = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]})
        ans = re.findall(r"-?\d+", r2.json()["candidates"][0]["content"]["parts"][0]["text"])[0]
        r3 = requests.post("https://www.agenthansa.com/api/agents/register/verify",
            json={"challenge_id": data["challenge_id"], "challenge_answer": int(ans)})
        d3 = r3.json()
        if "api_key" in d3:
            key = d3["api_key"]
            print(f"OK: {key[:20]}...")
        else:
            print(f"FALHA: {d3.get('detail', d3)}")
            time.sleep(30)
            continue
    elif "detail" in data and "rate" in str(data).lower():
        print(f"RATE LIMIT (esperando 60s)")
        time.sleep(60)
        continue
    else:
        print(f"ERRO: {data}")
        time.sleep(30)
        continue
    
    a = "red" if i <= 7 else "blue" if i <= 14 else "green"
    requests.patch("https://www.agenthansa.com/api/agents/alliance",
        headers={"Authorization": f"Bearer {key}"}, json={"alliance": a})
    print(f"  -> Alianca {a.upper()}")
    results[name] = key
    
    if i < 20:
        print("  -> Aguardando 60s...")
        time.sleep(60)

print("\n\n=== TODAS AS KEYS ===")
print("Cole no main.py dentro de AGENTS = [")
for n, k in results.items():
    print(f'    {{"name": "{n}", "key": "{k}", "alliance": "red"}},')
print("]")
