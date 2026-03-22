# agent_fun.py
import asyncio, json, sys, re
from typing import Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat  # pip install ollama

SYSTEM = (
    "You are a cheerful weekend helper. You can call MCP tools. "
    "You MUST call ONE tool at a time. Never batch tools. Never use 'sequence'. "
    "Available tools and their args: "
    "get_weather(latitude,longitude), book_recs(topic), random_joke(), random_dog(), trivia(). "
    "To call a tool, output ONLY this JSON (nothing else): "
    '{"action":"<tool_name>","args":{...}} '
    "After ALL tools are called, output ONLY: "
    '{"action":"final","answer":"..."}'
)

def extract_all_json(txt: str) -> List[Dict[str, Any]]:
    """Extract all top-level JSON objects from a string."""
    results = []
    decoder = json.JSONDecoder()
    i = 0
    while i < len(txt):
        # find next '{'
        start = txt.find('{', i)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(txt, start)
            results.append(obj)
            i = end
        except json.JSONDecodeError:
            i = start + 1
    return results

def llm_call(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    print("[LLM] main call → mistral:7b")
    resp = chat(model="mistral:7b", messages=messages, options={"temperature": 0.2})
    txt = resp["message"]["content"]
    print(f"[LLM] raw response: {txt[:300]}")
    objects = extract_all_json(txt)
    # keep only objects that have an "action" key (ignore tool result JSON in text)
    action_objects = [o for o in objects if "action" in o]
    if action_objects:
        return action_objects
    # no action JSON found → treat entire response as final answer
    return [{"action": "final", "answer": txt.strip()}]

async def main():
    server_path = sys.argv[1] if len(sys.argv) > 1 else "server_fun.py"
    exit_stack = AsyncExitStack()
    stdio = await exit_stack.enter_async_context(
        stdio_client(StdioServerParameters(command="python", args=[server_path]))
    )
    r_in, w_out = stdio
    session = await exit_stack.enter_async_context(ClientSession(r_in, w_out))
    await session.initialize()

    tools = (await session.list_tools()).tools
    tool_index = {t.name: t for t in tools}
    print("Connected tools:", list(tool_index.keys()))

    history = [{"role": "system", "content": SYSTEM}]
    try:
        while True:
            user = input("You: ").strip()
            if not user or user.lower() in {"exit","quit"}: break
            history.append({"role": "user", "content": user})

            pending: List[Dict[str, Any]] = []
            for _ in range(10):  # safety loop
                if not pending:
                    batch = llm_call(history)
                    # if batch has tool calls AND a final, drop the premature final
                    # so the LLM generates the answer after seeing real tool results
                    has_tools = any(b.get("action") not in ("final", None) and b.get("action") in tool_index for b in batch)
                    if has_tools:
                        pending = [b for b in batch if b.get("action") != "final"]
                    else:
                        pending = batch

                decision = pending.pop(0)
                print(f"[DECISION] {decision}")

                if decision.get("action") == "final":
                    answer = decision.get("answer", "")
                    if isinstance(answer, dict):
                        answer = json.dumps(answer, indent=2)
                    print("Agent:", answer)
                    history.append({"role": "assistant", "content": answer})
                    break

                tname = decision.get("action")
                args = decision.get("args", {})
                if tname not in tool_index:
                    print(f"[SKIP] unknown tool: {tname}")
                    continue

                result = await session.call_tool(tname, args)
                payload = result.content[0].text if result.content else result.model_dump_json()
                print(f"[TOOL] {tname} → {payload[:100]}")
                history.append({"role": "assistant", "content": f"[tool:{tname}] {payload}"})
    finally:
        await exit_stack.aclose()

if __name__ == "__main__":
    asyncio.run(main())