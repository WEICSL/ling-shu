# agent_service.py
# 完整的Agent服务，支持搜索和天气查询

import ollama
import json
import requests
from datetime import datetime
from typing import Dict, Any

# 尝试导入搜索库
try:
    from ddgs import DDGS

    SEARCH_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS

        SEARCH_AVAILABLE = True
    except ImportError:
        SEARCH_AVAILABLE = False


class WorkAgent:
    """主界面的干活Agent - 支持ReAct + Tool Calling + 联网搜索"""

    def __init__(self, model: str = "qwen2:7b"):
        self.model = model
        self.messages = []
        self.max_iterations = 5

    def _get_tools(self):
        """定义可用工具"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "执行数学计算",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "数学表达式，如 '2+3*4'",
                            }
                        },
                        "required": ["expression"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "获取当前日期和时间",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "搜索网络获取实时信息。用于查询新闻、资讯、实时事件等",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "返回结果数量",
                                "default": 5
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取城市天气",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称，如'北京'、'上海'",
                            }
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "text_transform",
                    "description": "文本转换",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["uppercase", "lowercase", "word_count"],
                                "description": "转换类型",
                            },
                            "text": {
                                "type": "string",
                                "description": "要处理的文本",
                            }
                        },
                        "required": ["action", "text"],
                    },
                },
            },
        ]

    # ========== 工具实现 ==========

    def calculator(self, expression: str) -> str:
        try:
            allowed = set("0123456789+-*/(). ")
            if not all(c in allowed for c in expression):
                return "表达式包含非法字符"
            result = eval(expression)
            return f"{expression} = {result}"
        except Exception as e:
            return f"计算错误：{e}"

    def get_current_time(self) -> str:
        now = datetime.now()
        return now.strftime("%Y年%m月%d日 %H:%M:%S")

    def web_search(self, query: str, max_results: int = 5) -> str:
        """网络搜索 - 使用DuckDuckGo"""
        if not SEARCH_AVAILABLE:
            return self._fallback_search(query)

        try:
            results = []

            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "href": r.get("href", "")
                    })

                    if len(results) >= max_results:
                        break

            if not results:
                return f"未找到「{query}」的相关信息"

            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(f"{i}. {r['title']}")
                formatted.append(f"   {r['body'][:200]}..." if len(r['body']) > 200 else f"   {r['body']}")
                formatted.append("")

            return "\n".join(formatted)

        except Exception as e:
            return self._fallback_search(query)

    def _fallback_search(self, query: str) -> str:
        """备用搜索方案"""
        try:
            # 使用 DuckDuckGo HTML 接口作为备用
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = []

                # 提取相关主题
                for topic in data.get("RelatedTopics", [])[:5]:
                    if isinstance(topic, dict) and "Text" in topic:
                        text = topic["Text"]
                        if text:
                            results.append(f"• {text[:150]}")

                if results:
                    return f"关于「{query}」的相关信息：\n" + "\n".join(results)

            return f"关于「{query}」的搜索结果：\n（搜索服务暂时不可用，请稍后再试）\n\n提示：运行 `pip install ddgs` 可获得完整搜索功能"

        except Exception as e:
            return f"搜索「{query}」失败：{str(e)[:100]}"

    def get_weather(self, city: str) -> str:
        """获取天气"""
        try:
            url = f"https://wttr.in/{city}?format=%C|%t|%w|%h&lang=zh"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.text.strip().split('|')
                weather_map = {
                    "Sunny": "☀️ 晴天", "Clear": "🌙 晴朗",
                    "Cloudy": "☁️ 多云", "Overcast": "☁️ 阴天",
                    "Rain": "🌧️ 雨天", "Light rain": "🌦️ 小雨",
                    "Moderate rain": "🌧️ 中雨", "Heavy rain": "⛈️ 大雨",
                    "Snow": "❄️ 雪天", "Light snow": "❄️ 小雪",
                    "Mist": "🌫️ 雾天", "Fog": "🌫️ 雾天",
                }

                weather_en = data[0] if data else ""
                weather_cn = weather_map.get(weather_en, weather_en)
                temp = data[1] if len(data) > 1 else ""
                wind = data[2] if len(data) > 2 else ""
                humidity = data[3] if len(data) > 3 else ""

                result = f"📍 {city}天气：{weather_cn}\n"
                if temp:
                    result += f"🌡️ 温度：{temp}\n"
                if wind:
                    result += f"💨 风力：{wind}\n"
                if humidity:
                    result += f"💧 湿度：{humidity}"
                return result
            return f"无法获取{city}的天气信息"
        except Exception as e:
            return f"获取天气失败：{e}"

    def text_transform(self, action: str, text: str) -> str:
        if action == "uppercase":
            return text.upper()
        elif action == "lowercase":
            return text.lower()
        elif action == "word_count":
            return f"字数：{len(text)}"
        return f"未知操作：{action}"

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        tool_map = {
            "calculator": self.calculator,
            "get_current_time": self.get_current_time,
            "web_search": self.web_search,
            "get_weather": self.get_weather,
            "text_transform": self.text_transform,
        }

        if name not in tool_map:
            return f"未知工具：{name}"

        try:
            if name == "web_search":
                return tool_map[name](arguments.get("query", ""), arguments.get("max_results", 5))
            elif name == "get_weather":
                return tool_map[name](arguments.get("city", ""))
            elif name == "text_transform":
                return tool_map[name](arguments.get("action", ""), arguments.get("text", ""))
            elif name == "calculator":
                return tool_map[name](arguments.get("expression", ""))
            elif name == "get_current_time":
                return tool_map[name]()
            else:
                return tool_map[name](**arguments)
        except Exception as e:
            return f"工具执行错误：{e}"

    def chat(self, user_input: str, stream_callback=None) -> str:
        """处理用户输入"""
        self.messages.append({"role": "user", "content": user_input})

        for iteration in range(self.max_iterations):
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self._get_tools(),
                stream=False
            )

            message = response['message']

            if message.get('tool_calls'):
                self.messages.append(message)

                for tool_call in message['tool_calls']:
                    func_name = tool_call['function']['name']
                    arguments = tool_call['function']['arguments']

                    result = self.execute_tool(func_name, arguments)

                    self.messages.append({
                        "role": "tool",
                        "content": result
                    })
            else:
                final_answer = message['content']
                self.messages.append(message)

                if stream_callback:
                    for char in final_answer:
                        stream_callback(char)
                return final_answer

        error_msg = "处理超时，请简化问题"
        if stream_callback:
            for char in error_msg:
                stream_callback(char)
        return error_msg

    def reset(self):
        self.messages = []


# 全局实例
work_agent = WorkAgent()


def get_agent_response_stream(user_input: str):
    """
    生成器函数，用于Django流式响应
    返回格式：SSE (Server-Sent Events)
    """
    output_chunks = []

    def callback(chunk):
        output_chunks.append(chunk)

    # 调用agent处理
    work_agent.chat(user_input, stream_callback=callback)

    # 生成最终输出
    full_response = ''.join(output_chunks)

    # 流式输出
    for char in full_response:
        yield f"data: {json.dumps({'content': char})}\n\n"

    yield f"data: {json.dumps({'done': True})}\n\n"