# Workplace Safety Incident Triage System

INF1103 Team Project Part 1. A terminal app that logs workplace safety incidents on a
construction site, enriches them with weather and AI-extracted hazard context, judges
severity, and decides an outcome.

```
io_manager -> ai_manager (Gemini + weather) -> logic_manager -> data_manager
```

## Setup

```bash
pip install -r library.txt
cp .env.example .env
```

Put your real `GEMINI_API_KEY` and `GROQ_API_KEY` in `.env`. The app still runs without
them — AI calls fall back to safe defaults and record the problem instead of crashing.

## Run

```bash
python main.py
```

## Run tests

```bash
pytest tests/
```

## Run with Docker

```bash
docker build -t inf1103project1 .
docker run -it --env-file .env inf1103project1
```

## Run the published image

Every merge to `main` publishes a new image to GitHub Container Registry.

```bash
docker pull ghcr.io/inf1103team6/inf1103project1:latest
docker run -it --env-file .env ghcr.io/inf1103team6/inf1103project1:latest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit format and the
day-to-day git flow.
