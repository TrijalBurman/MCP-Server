#!/usr/bin/env python3
"""Evaluation suite for the Knowledge Copilot.
Tests:
1. Health checks for both services
2. Memory write -> read round-trip
3. Decision log append + read
4. Note add + list
5. Agent chat query with tool execution

Usage:
    python3 evaluation/eval_retrieval.py [--agent-url http://localhost:8001] [--mcp-url http://localhost:8000]
"""
import argparse
import json
import sys
import time

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx


def call_agent(agent_url: str, message: str, history: list = None) -> dict:
    with httpx.Client(timeout=300) as client:
        resp = client.post(
            f"{agent_url}/chat",
            json={"message": message, "history": history or []},
        )
        resp.raise_for_status()
        return resp.json()


def call_mcp_tool(mcp_url: str, tool: str, params: dict = None) -> dict:
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{mcp_url}/mcp/tools/call",
            json={"tool": tool, "params": params or {}},
        )
        resp.raise_for_status()
        return resp.json().get("result", {})


def test_health(agent_url: str, mcp_url: str) -> bool:
    print("[1/5] Health checks...")
    try:
        with httpx.Client(timeout=10) as client:
            r1 = client.get(f"{agent_url}/health")
            r2 = client.get(f"{mcp_url}/health")
        assert r1.json().get("status") == "ok", "Agent unhealthy"
        assert r2.json().get("status") == "ok", "MCP server unhealthy"
        print("  PASS ✓: Both services healthy")
        return True
    except Exception as e:
        print(f"  FAIL ✗: {e}")
        return False


def test_memory_write_read(mcp_url: str) -> bool:
    print("[2/5] Memory write -> read round-trip...")
    try:
        ts = str(int(time.time()))
        call_mcp_tool(mcp_url, "write_memory", {
            "section": f"eval_test_{ts}",
            "content": f"Evaluation test content recorded at timestamp {ts}."
        })
        result = call_mcp_tool(mcp_url, "read_memory", {"section": f"eval_test_{ts}"})
        content = result.get("content", "")
        assert ts in content, f"Written content not found: {content}"
        print(f"  PASS ✓: Memory round-trip successful (section: eval_test_{ts})")
        return True
    except Exception as e:
        print(f"  FAIL ✗: {e}")
        return False


def test_decision_log(mcp_url: str) -> bool:
    print("[3/5] Decision log append + read...")
    try:
        ts = str(int(time.time()))
        title = f"Eval Decision {ts}"
        call_mcp_tool(mcp_url, "log_decision", {
            "title": title,
            "rationale": "Logged by automated evaluation suite.",
            "outcome": "Verified successfully.",
        })
        decisions = call_mcp_tool(mcp_url, "read_decisions", {"limit": 50})
        titles = [d["title"] for d in decisions.get("decisions", [])]
        assert title in titles, f"Decision '{title}' not found in {titles}"
        print(f"  PASS ✓: Decision logged and retrieved successfully")
        return True
    except Exception as e:
        print(f"  FAIL ✗: {e}")
        return False


def test_notes(mcp_url: str) -> bool:
    print("[4/5] Note add + list...")
    try:
        ts = str(int(time.time()))
        title = f"Eval Note {ts}"
        call_mcp_tool(mcp_url, "add_note", {
            "title": title,
            "body": f"This is an automated test note created at {ts}.",
            "tags": ["eval", "test"],
        })
        notes = call_mcp_tool(mcp_url, "list_notes", {})
        note_titles = [n["title"] for n in notes.get("notes", [])]
        assert title in note_titles, f"Note '{title}' not found in {note_titles}"
        print(f"  PASS ✓: Note saved and listed successfully")
        return True
    except Exception as e:
        print(f"  FAIL ✗: {e}")
        return False


def test_agent_chat(agent_url: str) -> bool:
    print("[5/5] Agent ReAct Chat Loop (testing Qwen2.5:7b live)...")
    try:
        result = call_agent(agent_url, "Give me a summary of our current project status.")
        answer = result.get("answer", "")
        steps = result.get("steps", 0)
        trace = result.get("trace", [])
        print(f"  Agent took {steps} step(s).")
        for i, s in enumerate(trace, 1):
            if s.get("action"):
                print(f"    Step {i} Action: {s['action']}({s.get('action_input')})")
        print(f"  Answer preview: {answer[:180]}...")
        assert len(answer) > 10, "Empty or too short answer received"
        print("  PASS ✓: Agent ReAct loop functioning properly!")
        return True
    except Exception as e:
        print(f"  FAIL ✗: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Evaluate the Knowledge Copilot")
    parser.add_argument("--agent-url", default="http://localhost:8001")
    parser.add_argument("--mcp-url", default="http://localhost:8000")
    args = parser.parse_args()

    print("=" * 60)
    print("  Knowledge Copilot — Full Evaluation Suite")
    print(f"  Agent:  {args.agent_url}")
    print(f"  MCP:    {args.mcp_url}")
    print("=" * 60)

    results = [
        test_health(args.agent_url, args.mcp_url),
        test_memory_write_read(args.mcp_url),
        test_decision_log(args.mcp_url),
        test_notes(args.mcp_url),
        test_agent_chat(args.agent_url),
    ]

    passed = sum(results)
    total = len(results)
    print("=" * 60)
    print(f"  Results: {passed}/{total} tests passed")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
