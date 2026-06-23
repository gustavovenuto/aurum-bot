import requests, re, time, sys

GEMINI_KEY = "AIzaSyBp_jNBc6yrIJGXD1gAwZyHJUfRzdyoIu4"
START = int(sys.argv[1]) if len(sys.argv) > 1 else 2
END = int(sys.argv[2]) if len(sys.argv) > 2 else 20

for i in range(START, END + 1):
    name = f"Aurum-{i:02d}"
    print(f"\n[{i}/{END}] Registrando {name}...")
    
    r = requests.post("https://www.agenthansa.com/api/agents/register",
        json={"name": name, "description": f"AI agent #{i}"})
    data = r.json()
    
    if "api_key" in data:
        key = data["api_key"]
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
        else:
            print(f"  ERRO: {d3}")
            continue
    else:
        print(f"  ERRO: {data}")
        continue
    
    a = "red" if i <= 7 else "blue" if i <= 14 else "green"
    requests.patch("https://www.agenthansa.com/api/agents/alliance",
        headers={"Authorization": f"Bearer {key}"}, json={"alliance": a})
    
    print(f"  KEY: {key}")
    print(f"  ALLIANCE: {a}")
    
    if i < END:
        print(f"  Aguardando 60s...")
        time.sleep(60)
