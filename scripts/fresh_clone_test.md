# Fresh-clone test checklist

Use a stopwatch. This test must start from a brand-new empty folder and follow only `README.md`.

## Setup

- [ ] Start the stopwatch immediately before cloning.
- [ ] Create a brand-new empty parent folder outside the existing working copy.
- [ ] Clone the repository into that folder.
- [ ] Confirm the clone contains no `data/real/`, real-player files, populated `.env`, or `results/cache.json`.
- [ ] Create `.env` one level above the clone, not inside it:

  ```env
  PORTKEY_API_KEY=YOUR_LOCAL_COURSE_KEY
  OPENAI_API_KEY=
  ```

- [ ] Confirm the clone itself contains no `.env` file.
- [ ] Create and activate the virtual environment.
- [ ] Run `python -m pip install -r requirements.txt`.
- [ ] Run `streamlit run app.py`.
- [ ] Stop the stopwatch after the app is usable. **Target: under 10 minutes.**

## No-key flow

- [ ] Temporarily remove or rename the parent `.env` so no key is available.
- [ ] Open the local app and click **Load sample data**.
- [ ] Tick sample attendance and click **Confirm attendance**.
- [ ] Confirm the AI controls show a friendly disabled/no-key state.
- [ ] Click **RUN DRAW** and confirm the draw completes without an API key.
- [ ] Confirm no real player data, key value, or absolute Windows username path appears in the app.

## Key-enabled AI flow

- [ ] Restore the `.env` one level above the clone; do not create one inside the clone.
- [ ] Reload the app and confirm the key source is not displayed as a secret value.
- [ ] Paste the sample chat and click **Read attendance**.
- [ ] Confirm the proposed attendance table appears and the **Token usage** panel shows input, cached input, output, calls, cache hits, and cost or the prices-not-set message.
- [ ] Confirm attendance and run the draw.
- [ ] Click **Write announcement** and confirm an announcement is produced without ratings.
- [ ] Click **Verify this draw** and confirm the result shows **VERIFIED: MATCH**.

## Hygiene and privacy

- [ ] From the clone, run `python scripts/secret_check.py`; confirm it passes.
- [ ] Search the clone and generated outputs for real player data, populated `.env`, API-key-looking values, `data/real/`, photos, and `results/cache.json`; confirm none are present.
- [ ] Confirm the public receipt and announcement contain no ratings.
- [ ] Confirm the parent `.env` is outside the clone and is not included in any commit or downloaded artifact.
- [ ] Record elapsed time, operating system, Python version, and any failed checkbox here:

  ```text
  Date:
  OS:
  Python:
  Elapsed:
  Result:
  Notes:
  ```
