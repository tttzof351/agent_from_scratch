"""
    Интерактивный агент с инструментами чтения, записи файлов и выполнения Bash-команд.
"""
import json
import os
import subprocess
from itertools import islice
from pathlib import Path
from dotenv import load_dotenv

import urllib.request
import urllib.error
import shutil

BOLD = '\033[1m'
ITALIC = '\033[3m'
GREEN = '\033[92m'
RED = '\033[91m'
GRAY = '\033[90m'
CYAN = '\033[96m'
BLUE = '\033[94m'
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

class ReadFileTool:
    def getName(self) -> str:
        return "read_file_tool"

    def getScheme(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.getName(),
                "description": "\n".join([
                    "Read a range of lines from a UTF-8 text file",
                    "with aligned, zero-padded absolute line numbers.",
                    "Relative paths use the current working directory."
                ]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file to read."},
                        "start_line": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1,
                            "description": "First line to read, numbered from 1."
                        },
                        "offset": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 200,
                            "description": "Maximum number of lines to read."
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False
                }
            }
        }

    def __call__(self, path: str, start_line: int = 1, offset: int = 200) -> str:
        if type(start_line) is not int or start_line < 1:
            return "Error reading file: start_line must be a positive integer."
        if type(offset) is not int or offset < 1:
            return "Error reading file: offset must be a positive integer."
        try:
            with Path(path).open(encoding="utf-8") as file:
                lines = list(islice(file, start_line - 1, start_line - 1 + offset))
            if not lines:
                return ""
            width = max(3, len(str(start_line + len(lines) - 1)))
            return "\n".join(
                f"{number:0{width}d}: " + line.rstrip("\n")
                for number, line in enumerate(lines, start=start_line)
            )
        except (OSError, UnicodeError, ValueError) as error:
            return f"Error reading file: {error}"

class EditFileTool:
    def getName(self) -> str:
        return "edit_file_tool"

    def getScheme(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.getName(),
                "description": "\n".join([
                    "Edit a UTF-8 text file by replacing exactly one occurrence",
                    "of old_string with new_string.",
                    "An empty old_string creates a new file only if the path does not exist.",
                    "Parent directories must exist.",
                    "Relative paths use the current working directory."
                ]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file to edit or create."},
                        "old_string": {
                            "type": "string",
                            "description": "\n".join([
                                "Exact text to replace; must occur uniquely.",
                                "Use an empty string to create a new file."
                            ])
                        },
                        "new_string": {
                            "type": "string",
                            "description": "\n".join([
                                "Replacement text, or complete contents for a new file.",
                                "May be empty to delete the matched text."
                            ])
                        }
                    },
                    "required": ["path", "old_string", "new_string"],
                    "additionalProperties": False
                }
            }
        }

    def __call__(self, path: str, old_string: str, new_string: str) -> str:
        try:
            file_path = Path(path)
            if old_string == "":
                if file_path.exists() or file_path.is_symlink():
                    return f"Error editing file: path already exists: {path}"
                with file_path.open("x", encoding="utf-8", newline="") as file:
                    file.write(new_string)
                return f"File created: {path}"

            with file_path.open(encoding="utf-8", newline="") as file:
                content = file.read()
            match_index = content.find(old_string)
            if match_index == -1:
                return "Error editing file: old_string was not found."
            if content.find(old_string, match_index + 1) != -1:
                return "Error editing file: old_string is not unique."
            updated_content = content.replace(old_string, new_string, 1)
            with file_path.open("w", encoding="utf-8", newline="") as file:
                file.write(updated_content)
            return f"File edited: {path}"
        except (OSError, UnicodeError, ValueError) as error:
            return f"Error editing file: {error}"

class BashTool:
    def getName(self) -> str:
        return "bash_tool"

    def getScheme(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.getName(),
                "description": "\n".join([
                    "Execute a Bash command in the current working directory",
                    "with a 60-second timeout.",
                    "Returns exit code, stdout and stderr."
                ]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to execute."}
                    },
                    "required": ["command"],
                    "additionalProperties": False
                }
            }
        }

    def __call__(self, command: str) -> str:
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            return json.dumps({
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return "Error executing command: timed out after 60 seconds."
        except (OSError, ValueError) as error:
            return f"Error executing command: {error}"


if __name__ == "__main__":
    logs_dir = Path("logs")

    if logs_dir.exists():
        shutil.rmtree(logs_dir)

    logs_dir.mkdir()

    load_dotenv(Path(__file__).parent.with_name(".env"))

    tools = [ ReadFileTool(), EditFileTool(), BashTool() ]

    payload = {
        "model": os.environ["MODEL_NAME"],
        "tool_choice": "auto",
        "tools": [t.getScheme() for t in tools],
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
                    if tool.getName() == tool_name:
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
