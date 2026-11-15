<!-- Sufi -->

# How to run

All commands start from the repository root (the folder with `Dockerfile`).

## Where the data goes (read this first)

| `DATABASE_URL` | What happens |
|---|---|
| **not set** (the default) | The app works straight away and saves to local files in `data/`: `incidents.json`, `photos/`, `ai_cache.json`, `site_plan.json` and `app.db` (priorities). It says so when it starts. |
| a Postgres URL (e.g. Neon) | Everything is saved in that database and survives restarts. |
| a file path ending in `.db` | A SQLite database at that path. |
| set, but the database cannot be reached | The app prints `Warning: could not open the database (...)`, then carries on with local files. It never crashes and never prints the password. |

Without `GEMINI_API_KEY` and `GROQ_API_KEY` the app still runs, but every incident goes to **manual review** because
the AI steps cannot work. Put your own keys in `.env` (copy `.env.example`); never commit that file.

## 1. Docker (nothing to install)

Start Docker Desktop, then:

```bash
docker build -t inf1103-part2 .

# the automated tests (no API keys or network needed)
docker run --rm inf1103-part2 python -m pytest

# the sample batch of incidents, then exit (no keys, no database needed)
docker run --rm inf1103-part2 python main.py --batch tests/sample_batch.json

# the interactive menu, with your keys; mounting data/ keeps saved incidents between runs
docker run -it --env-file .env -v "$(pwd)/data:/app/data" -v "$(pwd)/photos:/app/photos" inf1103-part2
```

Put photos in the `photos/` folder, then type `photos/yourfile.jpg` at the photo prompt.

## 2. Terminal app on your machine

Python 3.11 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your keys
python main.py              # interactive menu
python main.py --batch tests/sample_batch.json
```

Menu option 1 asks for a photo path. Drag an image file into the Terminal window.

## 3. Website (GUI)

You need **two Terminal windows**.

```bash
# Terminal 1: the API on http://127.0.0.1:8000
python web_api.py

# Terminal 2: the dashboard on http://127.0.0.1:5173
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open **http://127.0.0.1:5173** in Chrome. Use `127.0.0.1`, not `localhost`.

- The dashboard starts empty. Go to **Log incident** to add one (takes 20-60 seconds).
- There is no login: the dashboard opens straight away.
- Press `Ctrl + C` in each terminal to stop.

To use the hosted API instead of Terminal 1:

```bash
cd frontend
VITE_API_URL=https://incident-triage-api.onrender.com npm run dev -- --host 127.0.0.1
```

The first load can take about a minute if Render is asleep.

## 4. Tests

```bash
python -m pytest -v            # all tests, offline
ruff check .                   # lint
python run_tests.py            # lint + tests + batch run + dashboard build + Docker, all offline
python run_tests.py --list     # every check with its owner and phase
```

The tests never call a live API: they use the hard-coded sample AI replies in `tests/fakes.py`, block the network and
write to a temporary folder. They also pass inside Docker (section 1).

## Problems

- **"Server offline" in the sidebar:** Terminal 1 is not running, or it showed an error.
- **No AI results, everything goes to "manual review":** check `GEMINI_API_KEY` and `GROQ_API_KEY` in `.env`.
- **"Warning: could not open the database":** check `DATABASE_URL` (Neon: use the pooled connection string). The app is
  using local files until you fix it.
- **`npm` permission error:** run `sudo chown -R $(whoami) ~/.npm` once.
- **Free Render server is slow:** it sleeps after 15 idle minutes. Open it a minute early.
- **Saved incidents vanished on Render:** the free plan wipes its disk. Set `DATABASE_URL` to a Neon database to keep them.

## Logs

Logs go to the console (in Docker: `docker logs <container>`), not to a file.
