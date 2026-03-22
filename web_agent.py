# web_agent.py
import asyncio, json, sys
from typing import Dict, Any, List, AsyncGenerator
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
    results = []
    decoder = json.JSONDecoder()
    i = 0
    while i < len(txt):
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
    resp = chat(model="mistral:7b", messages=messages, options={"temperature": 0.2})
    txt = resp["message"]["content"]
    objects = extract_all_json(txt)
    action_objects = [o for o in objects if "action" in o]
    if action_objects:
        return action_objects
    return [{"action": "final", "answer": txt.strip()}]

def sse(event: str, data: Any) -> str:
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"

async def run_agent(prompt: str) -> AsyncGenerator[str, None]:
    server_path = "server_fun.py"
    exit_stack = AsyncExitStack()
    try:
        stdio = await exit_stack.enter_async_context(
            stdio_client(StdioServerParameters(command="python", args=[server_path]))
        )
        r_in, w_out = stdio
        session = await exit_stack.enter_async_context(ClientSession(r_in, w_out))
        await session.initialize()

        tools = (await session.list_tools()).tools
        tool_index = {t.name: t for t in tools}

        history = [{"role": "system", "content": SYSTEM}]
        history.append({"role": "user", "content": prompt})

        yield sse("status", "Thinking...")

        pending: List[Dict[str, Any]] = []
        for _ in range(10):
            if not pending:
                yield sse("status", "Calling LLM...")
                batch = await asyncio.get_event_loop().run_in_executor(None, llm_call, history)
                has_tools = any(
                    b.get("action") not in ("final", None) and b.get("action") in tool_index
                    for b in batch
                )
                pending = [b for b in batch if b.get("action") != "final"] if has_tools else batch

            decision = pending.pop(0)
            action = decision.get("action")

            if action == "final":
                answer = decision.get("answer", "")
                if isinstance(answer, dict):
                    answer = json.dumps(answer, indent=2)
                yield sse("final", answer)
                break

            tname = action
            args = decision.get("args", {})

            if tname not in tool_index:
                yield sse("skip", {"tool": tname, "reason": "unknown tool"})
                continue

            yield sse("tool_call", {"tool": tname, "args": args})

            result = await session.call_tool(tname, args)
            payload = result.content[0].text if result.content else result.model_dump_json()

            # try to parse payload as JSON for nicer display
            try:
                payload_display = json.loads(payload)
            except Exception:
                payload_display = payload

            yield sse("tool_result", {"tool": tname, "result": payload_display})
            history.append({"role": "assistant", "content": f"[tool:{tname}] {payload}"})

    except Exception as e:
        yield sse("error", str(e))
    finally:
        await exit_stack.aclose()

class PromptRequest(BaseModel):
    prompt: str

@app.post("/run")
async def run_endpoint(req: PromptRequest):
    return StreamingResponse(run_agent(req.prompt), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
