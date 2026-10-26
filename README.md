Local app, run instructions below

# Sunday League Fair Draw

A privacy-conscious Sunday-league app that uses code to create reproducible, fair teams and optional AI to read attendance chat and write announcements.

## The problem

Informal attendance messages are ambiguous, roster changes are easy to miss, and repeated teammate pairings can feel unfair. The app turns a confirmed roster and attendance list into a reproducible draw with an auditable receipt.

## Run it in 10 minutes

### Windows PowerShell

1. Clone the repository and enter the app folder:
   ```powershell
   git clone <repository-url>
   cd prediction-league-referee\sunday-league-fair-draw
   ```
2. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Create a `.env` file either inside this repository folder or one folder above it. Use either allowed key variable:
   ```env
   PORTKEY_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   ```
   The course key uses the `gpt-6-luna` model only. Never commit `.env`.
5. Start the app:
   ```powershell
   streamlit run app.py
   ```
6. Click **Load sample data**, tick attendance, click **Confirm attendance**, and click **RUN DRAW**.

### Mac/Linux

1. Clone and enter the app folder:
   ```bash
   git clone <repository-url>
   cd prediction-league-referee/sunday-league-fair-draw
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. Create `.env` inside the repository folder or one folder above it:
   ```env
   PORTKEY_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   ```
   The course key uses `gpt-6-luna` only. Never commit `.env`.
5. Start the app:
   ```bash
   streamlit run app.py
   ```
6. Click **Load sample data**, tick attendance, confirm the squad, and run the draw.

The draw works without an API key. Only the optional AI chat reader and announcement writer require a key.

For the report-only safety demonstration panel, set `FAIRDRAW_DEMO=1` before starting Streamlit. It is hidden by default; unset the variable for normal use.

## Run the safety demos

Windows PowerShell:

```powershell
$env:FAIRDRAW_DEMO="1"
streamlit run app.py
```

Mac/Linux:

```bash
FAIRDRAW_DEMO=1 streamlit run app.py
```

Open **Safety demos (for the report)** and use the four demo controls. These exercise the real guards, parsers, verifiers, and budget refusal path. The panel is hidden unless `FAIRDRAW_DEMO=1` is set.

## What the app does and does not do

The deterministic Python draw engine creates teams, balances the selected objectives, and verifies receipts. AI is optional: it reads untrusted attendance chat and can write a short announcement. AI does not choose teams, assign ratings, edit the roster, approve payments, or send messages.

## How the draw works

The app takes the confirmed attendees, roster ratings, goalkeeper roles, and recent history. It generates candidate splits, scores them for balance and repeat pairings, and uses a published seed to select a reproducible result. The receipt records the seed, draw number, engine version, inputs hash, teams, and metrics so the result can be verified later.

## Safety and privacy

Chat text is treated as untrusted data. Code parses timestamps and senders, validates claims and evidence, rejects unsupported actions, and requires organizer confirmation for third-party claims and guests. Ratings are kept out of public receipts. API keys belong only in the allowed `.env` locations and are never written into the repository. Trap tools and organizer actions are not available to chat messages.

## Run the tests

From the app folder:

```powershell
pytest -q --basetemp .pytest-run
```

## Run the simulation

The simulation calls the real draw engine and compares random, balance-only, and balance-plus-memory methods:

```powershell
python scripts/simulate.py
```

Use a private roster without committing it:

```powershell
python scripts/simulate.py --roster data/real/roster.csv
```

## Run the evaluation

The labeled-chat evaluation requires a configured API key:

```powershell
python scripts/run_eval.py
```

The cost experiment and scaling report are also available:

```powershell
python scripts/cost_experiment.py
python scripts/scale_costs.py
```

## Files

- `app.py` — Streamlit application.
- `fairdraw/draw.py` — deterministic seeded draw engine.
- `fairdraw/pipeline.py` — attendance pipeline.
- `fairdraw/chat_splitter.py`, `attendance_agent.py`, `claims.py` — chat parsing and claim handling.
- `fairdraw/verifier.py`, `guards.py` — verification and defense checks.
- `fairdraw/announce_agent.py`, `command_agent.py` — optional organizer AI features.
- `data/sample_roster.csv`, `data/sample_history.json` — fake sample data.
- `data/labeled/` — reviewed evaluation fixtures.
- `data/real/` — private real roster, history, and photos; never commit this folder.
- `scripts/` — simulation, evaluation, and cost reports.
- `results/` — generated logs and reports.
- `DESIGN.md` — design-system notes.

## Sample and real data

All sample data is FAKE. Put real roster data, history, and photos in `data/real/`. That folder is ignored and must never be committed.

