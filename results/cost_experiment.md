# Cost experiment

**Status: REFUSED before any model call.**

- Planned calls: `36`

Refused before any model call: variant A requires 30 calls in one run, above the per-run limit of 8.

| Variant | Planned calls |
|---|---:|
| A_one_call_per_message | 30 |
| B_batches_of_25 | 2 |
| C_batches_plus_cache | 4 |
