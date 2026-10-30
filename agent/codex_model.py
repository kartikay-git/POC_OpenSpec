"""LangChain model transport using the signed-in, official Codex CLI.

This is structured-output tool emulation, not native OpenAI API tool calling.
The CLI returns one decision; LangChain executes the actual project tool.
No OAuth token is read or copied by this module.
"""
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

DECISION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "tool": {"type": "string", "description": "Exactly one supplied tool name, or empty when finished."},
        "arguments_json": {"type": "string", "description": "JSON-encoded object of arguments for that tool; use {} when finished."},
        "final": {"type": "string", "description": "Brief final answer when finished; empty when calling a tool."},
    },
    "required": ["tool", "arguments_json", "final"],
}


class CodexChatModel(BaseChatModel):
    model: str = "gpt-6-luna"
    reasoning_effort: str = "low"
    timeout: float = 600
    executable: str = "codex"
    log_directory: Path | None = None
    stage: str = "model"
    bound_tools: list[Any] = Field(default_factory=list, exclude=True)

    @property
    def _llm_type(self):
        return "codex-cli-structured-tool-adapter"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        if tool_choice not in (None, "auto"):
            raise ValueError("This adapter supports automatic single-tool decisions only.")
        return self.model_copy(update={"bound_tools": list(tools)})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if stop:
            raise ValueError("Codex CLI transport does not support stop sequences.")
        schemas = [convert_to_openai_tool(tool) for tool in self.bound_tools]
        history = [message.model_dump(mode="json") for message in messages]
        prompt = (
            "Act as the decision model inside a LangChain loop. All relevant context is below. "
            "Do not use Codex native tools, inspect the filesystem, or execute any command. "
            "To read or write project files, RETURN a tool decision in the final JSON schema. "
            "The host LangChain loop will execute it and return the result in the next request. "
            "Choose exactly one supplied tool or finish with an empty tool. Arguments must match "
            "its schema. All file content must be complete and preserve formatting. "
            "A tool decision IS your way to act: for example, to read a file return "
            "{\"tool\":\"read_file\",\"arguments_json\":\"{\\\"path\\\":\\\"application/todos/views.py\\\"}\",\"final\":\"\"}. "
            "If context is missing, select read_file yourself; do not ask the host to call it. "
            "If asked to create an artifact or edit source, select the supplied write tool with "
            "the complete content. Do not finish until the requested operation has a successful tool result. "
            "Never claim a write or test happened unless its tool result is in the history.\n"
            + "AVAILABLE LANGCHAIN TOOLS:\n" + json.dumps(schemas, ensure_ascii=False)
            + "\nCONVERSATION:\n" + json.dumps(history, ensure_ascii=False)
        )
        decision, events = self._request(prompt)
        # A native action means the transport violated its role; fail rather than
        # misrepresenting native Codex actions as LangChain tool execution.
        for event in events:
            item = event.get("item", {})
            if item.get("type") in {"command_execution", "file_change", "mcp_tool_call", "web_search", "collab_tool_call"}:
                raise RuntimeError("Codex attempted a native action; this POC requires LangChain tools.")
        if set(decision) != {"tool", "arguments_json", "final"} or not all(isinstance(v, str) for v in decision.values()):
            raise ValueError("Invalid Codex decision envelope.")
        arguments = json.loads(decision["arguments_json"])
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object.")
        name = decision["tool"]
        calls = []
        if name:
            available = {tool.name: tool for tool in self.bound_tools}
            if name not in available:
                raise ValueError(f"Codex selected an unavailable tool: {name}")
            available[name].args_schema.model_validate(arguments)
            calls = [{"name": name, "args": arguments, "id": "codex_" + uuid.uuid4().hex, "type": "tool_call"}]
        elif arguments:
            raise ValueError("A final response cannot carry tool arguments.")
        usage = next((event.get("usage", {}) for event in reversed(events) if event.get("type") == "turn.completed"), {})
        message = AIMessage(content=decision["final"], tool_calls=calls,
                            response_metadata={"model": self.model, "transport": self._llm_type, "codex_usage": usage})
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _request(self, prompt):
        executable = shutil.which(self.executable)
        if not executable:
            raise RuntimeError("Codex CLI not found. Install it and run codex login, or set CODEX_EXECUTABLE.")
        # An empty temporary working directory keeps the CLI away from the app.
        # Its output file is written by the CLI host, not a model file-edit tool.
        with tempfile.TemporaryDirectory(prefix="openspec-codex-") as folder:
            directory = Path(folder)
            schema = directory / "decision.schema.json"
            output = directory / "decision.json"
            schema.write_text(json.dumps(DECISION_SCHEMA), encoding="utf-8")
            argv = [executable, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                    "--sandbox", "read-only", "--color", "never", "--json",
                    "--model", self.model, "-c", f'model_reasoning_effort="{self.reasoning_effort}"',
                    "-c", 'web_search="disabled"', "--output-schema", str(schema),
                    "--output-last-message", str(output)]
            for feature in ("shell_tool", "multi_agent", "apps", "plugins", "browser_use", "computer_use", "image_generation", "hooks"):
                argv.extend(["--disable", feature])
            argv.append("-")
            try:
                result = subprocess.run(argv, input=prompt, cwd=directory, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace", timeout=self.timeout, shell=False)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Codex model request exceeded {self.timeout}s.") from exc
            if self.log_directory:
                self.log_directory.mkdir(parents=True, exist_ok=True)
                identifier = f"{self.stage}-{uuid.uuid4().hex[:10]}"
                (self.log_directory / f"{identifier}.jsonl").write_text(result.stdout, encoding="utf-8")
                (self.log_directory / f"{identifier}.stderr.txt").write_text(result.stderr, encoding="utf-8")
            if result.returncode or not output.exists():
                raise RuntimeError(f"Codex request failed ({result.returncode}). {result.stderr[-2000:]} {result.stdout[-2000:]}")
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
            if any(event.get("type") in {"turn.failed", "error"} for event in events):
                raise RuntimeError("Codex returned an error; see the recorded transport events.")
            return json.loads(output.read_text(encoding="utf-8")), events


def configured_model(**kwargs):
    return CodexChatModel(model=os.environ.get("CODEX_MODEL", "gpt-6-luna"),
                          reasoning_effort=os.environ.get("CODEX_REASONING_EFFORT", "high"),
                          timeout=float(os.environ.get("CODEX_TIMEOUT", "600")),
                          executable=os.environ.get("CODEX_EXECUTABLE", "codex"), **kwargs)
