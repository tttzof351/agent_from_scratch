"""
    Базовый пример запросов к LLM
"""

import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

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


if __name__ == "__main__":
    logs_dir = Path("logs")

    if logs_dir.exists():
        shutil.rmtree(logs_dir)

    logs_dir.mkdir()

    load_dotenv(Path(__file__).parent.with_name(".env"))

    payload = {
        "model": os.environ["MODEL_NAME"],
        "messages": [
            {"role": "system", "content": "You are a AI assistant."},
            {"role": "user", "content": "Напиши hello world"},
        ],
    }

    response: dict = chat_completions_request(payload)
    print(json.dumps(response, indent=4, ensure_ascii=False))
