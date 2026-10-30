import json
from types import SimpleNamespace

import pytest
from langchain_core.tools import tool
from agent.codex_model import CodexChatModel


@tool
def save_text(content: str):
    """Save supplied text."""
    return "saved " + content


def test_decision_round_trip_preserves_source_and_uses_langchain(monkeypatch):
    from langchain.agents import create_agent
    source = 'def example():\n    return "Unicode: café"\n'
    calls = []
    def request(self, prompt):
        calls.append(json.loads(prompt.split("CONVERSATION:\n")[1]))
        if len(calls) == 1:
            return {"tool": "save_text", "arguments_json": json.dumps({"content": source}), "final": ""}, []
        return {"tool": "", "arguments_json": "{}", "final": "Finished"}, []
    monkeypatch.setattr(CodexChatModel, "_request", request)
    result = create_agent(CodexChatModel(), tools=[save_text]).invoke({"messages": [{"role": "user", "content": "Save source"}]})
    assert any(message.type == "tool" and message.content == "saved " + source for message in result["messages"])
    assert calls[1][-1]["type"] == "tool"
    assert result["messages"][-1].content == "Finished"


@pytest.mark.parametrize("decision,events,error", [
    ({"tool": "shell", "arguments_json": "{}", "final": ""}, [], "unavailable tool"),
    ({"tool": "save_text", "arguments_json": "[]", "final": ""}, [], "must be an object"),
    ({"tool": "", "arguments_json": '{"x":1}', "final": "done"}, [], "cannot carry"),
    ({"tool": "", "arguments_json": "{}", "final": "done"}, [{"item": {"type": "command_execution"}}], "native action"),
])
def test_invalid_or_native_actions_are_rejected(monkeypatch, decision, events, error):
    monkeypatch.setattr(CodexChatModel, "_request", lambda self, prompt: (decision, events))
    with pytest.raises((ValueError, RuntimeError), match=error):
        CodexChatModel().bind_tools([save_text]).invoke("Do work")


def test_cli_transport_is_read_only_and_logs_events(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.codex_model.tempfile.tempdir", str(tmp_path))
    monkeypatch.setattr("agent.codex_model.shutil.which", lambda executable: "codex.exe")
    def execute(argv, **kwargs):
        assert kwargs["shell"] is False
        assert argv[argv.index("--sandbox") + 1] == "read-only"
        assert "--ignore-user-config" in argv and "--ephemeral" in argv
        assert "shell_tool" in argv and "multi_agent" in argv and "plugins" in argv
        assert argv[-1] == "-" and kwargs["input"] == "prompt"
        from pathlib import Path
        Path(argv[argv.index("--output-last-message") + 1]).write_text('{"tool":"","arguments_json":"{}","final":"OK"}')
        return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed","usage":{"input_tokens":10}}\n', stderr="")
    monkeypatch.setattr("agent.codex_model.subprocess.run", execute)
    response, events = CodexChatModel(log_directory=tmp_path)._request("prompt")
    assert response["final"] == "OK"
    assert events[0]["usage"]["input_tokens"] == 10
    assert len(list(tmp_path.glob("*.jsonl"))) == 1
