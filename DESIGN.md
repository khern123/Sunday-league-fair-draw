# Sunday League Fair Draw — design system

## Visual direction

The interface uses a dark, original football-night visual language: navy surfaces, cyan and blue actions, indigo only in gradients, and high-contrast white text. The UI is intentionally mobile-first and keeps the next action obvious: confirm the squad, run the draw, verify it, then share it.

## Tokens

The single source of truth is `assets/theme.css`:

- Background: `#050B1A`; surfaces: `#0D1B3A` and `#132850`.
- Text: `#F2F7FF`; muted text: `#A9BCDD`.
- Accent blue: `#3B82F6`; cyan: `#22D3EE`; indigo: `#5B3DF5` for gradients only.
- Gold is reserved for kickoff and key numbers; green is reserved for successful verification; red is reserved for errors.
- Spacing follows a 4px scale; controls have a minimum 44px target; focus rings are cyan.

## Reusable components

`fairdraw_ui/components.py` owns escaped, inline SVG/HTML components: shirts, crests, chips, stat cards, progress rings, section headers, and badges. User text is escaped before it enters markup. Shirt SVGs use a real clipped T-shirt silhouette and deterministic kit patterns.

## Screens

- **Tonight / Squad:** matchday hero, attendance counter, player cards, chat-reader status, and one state-driven primary action.
- **Draw:** team setup, seeded reveal, pitch cards, fairness metrics, certificate, verification, and a rating-free share card.
- **History:** newest-first fixture feed, horizontally scrollable teammate matrix, and neutral history insights.
- **Verify:** public receipt verification with plain-English MATCH/MISMATCH explanation.

## Screenshot checklist

1. Tonight before loading: open app → sample mode → capture hero and empty/loading state.
2. Squad board: Load sample data → Tonight → capture all player cards and attendance counter.
3. Squad locked: select/clear attendance → Confirm squad → capture locked banner.
4. Draw setup: open Draw → capture team-count, seed mode, disabled/ready primary action.
5. Settled teams: Confirm squad → Run draw → capture pitch cards and fairness cards.
6. Verified certificate: open receipt → Verify this draw → capture the green MATCH badge.
7. History: open History → Past nights → capture fixture feed and matrix.
8. Share card: completed draw → Share/Matchday card → capture the rating-free announcement card.
