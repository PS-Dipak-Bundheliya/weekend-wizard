# Weekend Wizard

An AI-powered weekend planning assistant. Ask it to plan your weekend and it fetches real-time weather, book recommendations, jokes, dog pics, and trivia — all in one response.

## Demo Recording

[Watch the demo on Google Drive](https://drive.google.com/file/d/1UmhyXTNW78eXTqgBIFRJENDkpfl3EJVv/view?usp=sharing)

## Example Prompt

> *"Plan a cozy Saturday in New York at (40.7128, -74.0060). Include the current weather, 2 book ideas about mystery, one joke, and a dog pic."*

## Tech Stack

- **Frontend:** HTML + Vanilla JS (dark UI, real-time streaming)
- **Backend:** Python + FastAPI
- **LLM:** Mistral 7B via [Ollama](https://ollama.com)
- **Tools:** [MCP](https://modelcontextprotocol.io) server with 5 public APIs

## Prerequisites

- Python 3.8+
- [Ollama](https://ollama.com) installed and running

## Setup

```bash
# 1. Clone and enter the project
cd weekend-wizard

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install mcp ollama fastapi uvicorn requests

# 4. Pull the model
ollama pull mistral:7b
```

## Run

```bash
# Start Ollama (if not already running)
ollama serve

# Start the web server
python web_agent.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## CLI Mode

```bash
python agent_fun.py server_fun.py
```

## Available Tools

| Tool | API | Description |
|------|-----|-------------|
| `get_weather` | Open-Meteo | Current weather by coordinates |
| `book_recs` | Open Library | Book recommendations by topic |
| `random_joke` | JokeAPI | A safe, single-line joke |
| `random_dog` | Dog CEO | A random dog image |
| `trivia` | Open Trivia DB | A multiple-choice trivia question |

## Project Structure

```
weekend-wizard/
├── index.html      # Web UI
├── web_agent.py    # FastAPI server (port 8000)
├── agent_fun.py    # CLI version
└── server_fun.py   # MCP tool server
```
