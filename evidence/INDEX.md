# Evidence index

| Evidence item | Exact file name | What it shows | Report section | Slide | Status |
|---|---|---|---|---|---|
| Run trace | `run-trace-1440.png`, `run-trace-390.png` | Real pipeline timeline from splitter through verifiers | System flow / safety | Architecture | missing |
| Attendance proposal | `attendance-proposal-1440.png`, `attendance-proposal-390.png` | Real sample-mode attendance board state | Attendance workflow | Demo | have |
| Squad board | `squad-board-1440.png`, `squad-board-390.png` | Roster attendance board and counter | User experience | Squad | have |
| Draw on pitch | `draw-pitch-1440.png`, `draw-pitch-390.png` | Real settled team pitch view | Draw engine | Draw | missing |
| Fairness cards | `fairness-cards-1440.png`, `fairness-cards-390.png` | Balance, pairings, and keeper-cover metrics | Fairness | Fairness | missing |
| VERIFIED badge | `verified-badge-1440.png`, `verified-badge-390.png` | Successful receipt verification | Verification | Trust | missing |
| MISMATCH badge | `mismatch-badge-1440.png`, `mismatch-badge-390.png` | Failed receipt verification and explanation | Verification / defenses | Trust | missing |
| Share card | `share-card-1440.png`, `share-card-390.png` | Public matchday announcement card without ratings | Sharing | Share | missing |
| Token panel | `token-panel-1440.png`, `token-panel-390.png` | Input, cached, output, calls, cost, and budget meter | AI usage / cost | Cost | missing |
| Defense log with attack | `defense-log-attack-1440.png`, `defense-log-attack-390.png` | Real app safety-demo panel captured; attack run still needs confirmation | Safety | Safety | partial |
| Bad-output fallback | `bad-output-fallback-1440.png`, `bad-output-fallback-390.png` | Invalid/invented model output rejected and fallback shown | Safety / failure modes | Safety | missing |
| Budget cap | `budget-cap-1440.png`, `budget-cap-390.png` | Friendly refusal when the call budget is reached | Cost controls | Safety | missing |
| Draw disabled before confirming | `draw-disabled-1440.png`, `draw-disabled-390.png` | Disabled draw control with its reason | Organizer controls | Demo | missing |
| Simulation table | `results/simulation_table.md` | 50-repeat comparison of methods A, B, and C | Evaluation | Results | have |
| Evaluation table | `results/eval_table.md` | Claim and final-attendance evaluation metrics | Evaluation | Results | have |
| Cost experiment table | `results/cost_experiment.md` | Variant cost/accuracy comparison or budget refusal | Cost analysis | Results | have |
| League night photo or screenshot | `league-night-permission.jpg` or `league-night-screenshot.png` | Real league-night context, with permission | Context / ethics | Context | missing — needs user |
| User quotes | `user-quotes.md` | Attributed or anonymized feedback with permission | User feedback | User feedback | missing — needs user |

## Capture rules

- UI screenshots must come from real sample-mode runs of the real app at 1440px and 390px.
- Do not include ratings in public receipts, share cards, or screenshots where ratings are hidden.
- Remove or avoid API keys, private player data, and absolute local paths.
- Keep written permission with any league-night photo or identifiable quote.
