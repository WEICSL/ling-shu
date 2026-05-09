import requests

API_KEY = 'sk-5679a772e93e422fb5b5ec7f6cd3c7a4'
API_URL = 'https://api.deepseek.com/v1/chat/completions'

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model":"deepseek-chat",
    "messages": [
        {"role": "system", "content": "你是一个 helpful 的助手"},
        {"role": "user", "content": "用Python写一个快速排序的代码"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000
}

response = requests.post(API_URL, json=data, headers=headers)
result = response.json()

print(result["choices"][0]["message"]["content"])