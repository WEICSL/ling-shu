import requests

API_KEY = "sk-5679a772e93e422fb5b5ec7f6cd3c7a4"
API_URL = "https://api.deepseek.com/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "user", "content": "讲一个简短的小故事"}
    ],
    "stream": True
}

response = requests.post(API_URL, json=data, headers=headers, stream=True)

for line in response.iter_lines():
    if line:
        line = line.decode("utf-8")
        if line.startswith("data: "):
            line = line[6:]
            if line == "[DONE]":
                break
            try:
                import json
                chunk = json.loads(line)
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta:
                        print(delta["content"], end="", flush=True)
            except:
                pass