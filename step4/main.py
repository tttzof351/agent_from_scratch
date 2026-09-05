"""
    Интерактивный диалог с LLM с сохранением истории в памяти
    и циклом выполнения вызовов инструмента со случайным прогнозом погоды.
"""

import json
import os
import random
import shutil
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

GREEN = '\033[92m'
RED = '\033[91m'
ENDC = '\033[0m'

request_counter = 0

def chat_completions_request(payload: dict, save_log: bool = True) -> dict:
    global request_counter

    api_key = os.environ["OPENROUTER_API_KEY"]

    body = json.dumps(payload).encode("utf-8")

    if save_log:
        with open(f"logs/{request_counter}_request.json", "w") as file:
            file.write(json.dumps(payload, indent=4, ensure_ascii=False))

    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as http_response:
        response = json.loads(http_response.read().decode("utf-8"))

    if save_log:
        with open(f"logs/{request_counter}_response.json", "w") as file:
            file.write(json.dumps(response, indent=4, ensure_ascii=False))

    request_counter += 1
    return response

class WeatherTool:
    def get_name(self) -> str:
        return "get_weather_tool"

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.get_name(),
                "description": "Get simulated weather for the specified city using a random preset.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name, for example: San Francisco, USA."
                        }
                    },
                    "required": ["city"],
                    "additionalProperties": False
                }
            }
        }

    def __call__(self, city: str) -> str:
        forecasts = [
            "Sunny, +24 °C, light wind.",
            "Cloudy, +18 °C, no precipitation.",
            "Rainy, +12 °C, gusty wind.",
            "Snowy, −3 °C, light wind."
        ]
        return f"Weather for {city}: {random.choice(forecasts)}"

if __name__ == "__main__":
    logs_dir = Path("logs")

    if logs_dir.exists():
        shutil.rmtree(logs_dir)

    logs_dir.mkdir()

    load_dotenv(Path(__file__).parent.with_name(".env"))

    tools = [ WeatherTool() ]

    payload = {
        "model": os.environ["MODEL_NAME"],
        "tool_choice": "auto",
        "tools": [t.get_schema() for t in tools],
        "messages": [
            {
                "role": "system",
                "content": "You are a AI assistant."
            }
        ]
    }

    next_messages = None
    while True:
        if next_messages is None:
            print(">>> ", end="")
            user_input = input()
            next_messages = [{
                "role": "user",
                "content": user_input
            }]

        payload["messages"] += next_messages

        response: dict = chat_completions_request(payload)

        message: dict = response["choices"][0]["message"]

        tool_calls: list = message.get("tool_calls", [])

        payload["messages"].append(message)
        if len(tool_calls) > 0:
            next_messages = []
            for tool_call in tool_calls:
                tool_id: str = tool_call["id"]
                tool_name: str = tool_call["function"]["name"]
                tool_args: dict = json.loads(tool_call["function"]["arguments"])

                for tool in tools:
                    if tool.get_name() == tool_name:
                        tool_answer: str = tool(**tool_args)
                        print(RED + f"Tool call {tool_name}")
                        tool_answer_message: dict = {
                            "role": "tool",
                            "content": tool_answer,
                            "tool_call_id": tool_id,
                        }
                        next_messages.append(tool_answer_message)
        else:
            next_messages = None
            content = message["content"]
            print(GREEN + content + ENDC)
