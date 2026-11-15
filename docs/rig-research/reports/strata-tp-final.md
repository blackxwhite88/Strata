# Strata tp final

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Final TP versus native comparison. Native R2 achieved 44.78 versus TP 13.69 whole-request tok/s on the matched first warm pair (3.27x), with identical paired text. Both runs started FAST and ended SLOW, with no per-pair state probe. Native used 8 GiB cache versus TP 32 GiB and later missed prefixes. TP fairness and sustained legs were incomplete. No universal or strictly state-matched engine speedup is established. Prefetch preserved the tested greedy outputs but increased host traffic and reduced observed warm speed.

## Retained tables

### Window A: one stream

| Arm | Enabled new switches | Cold decode tok/s | Warm decode tok/s | Cold ms/round | Warm ms/round | Output check | Performance result |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| A0 | None | 57.9 | 87.6 | 34.14 | 142.59 | PASS, both window-3 hashes | Baseline reproduced; FAST throughout probes |
| A1 | Copy stats | 47.9 | 34.8 | 41.25 | 359.18 | PASS, both A0 hashes | Slower observed; mixed host state prevents isolating counter overhead |
| A2 | Copy engine + stats | 37.1 | 41.1 | 53.34 | 304.00 | PASS, both A0 hashes | Warm decode +18.1% vs A1, cold slower; FAST before, SLOW after |
| A3 | Copy engine + stats + prefetch | 22.9 | 24.9 | 86.39 | 501.04 | PASS, both A0 hashes | Hurt observed speed; SLOW before and after; exclude prefetch |

### Window A: one stream

| Arm | Before memcpy, GB/s (three samples) | After memcpy, GB/s (three samples) |
| --- | --- | --- |
| FAST gate, production up | 9.63, 9.85, 9.69 | — |
| A0 | 9.18, 9.20, 9.67 | 9.92, 9.66, 9.91 |
| A1 | 9.58, 9.52, 9.63 | 9.02, 3.58, 9.86 |
| A2 | 9.68, 9.56, 9.72 | 3.52, 3.54, 3.54 |
| A3 | 3.50, 3.42, 3.49 | 3.56, 3.52, 3.53 |

### Copy measurements

| Arm/request | Host GB/card (card 0 = card 1) | Mean wait ms/window, card 0 | Card 1 |
| --- | ---: | ---: | ---: |
| A1 cold | 28.751 | 17.43 | 17.41 |
| A1 warm | 38.001 | 301.52 | 301.49 |
| A2 cold | 28.751 | 30.26 | 30.04 |
| A2 warm | 38.001 | 246.99 | 245.45 |
| A3 cold | 77.536 | 62.00 | 57.73 |
| A3 warm | 76.462 | 440.82 | 336.44 |

### Window B: two different conversations

| Leg | Completed work | Decode tok/s | Qualification |
| --- | --- | --- | --- |
| B0: copy engine + counters | Both cold primes; paired round 1 | Cold 37.1 / 31.4; warm pair below | INCOMPLETE: round 2 budget-censored; round 3, third read and sustained leg not reached |
| B1: B0 + read interleave | First cold prime; partial second prime | First cold 36.1 | INCOMPLETE: budget-censored before paired decoding |
| Initial R2 attempt | Launch only | No inference | Harness FAIL; corrected in authorized window C |

### Window B: two different conversations

| Stream | Engine decode tok/s | TTFT, seconds | Reused tokens | Largest SSE gap, seconds | Marker / 512 tokens |
| --- | ---: | ---: | ---: | ---: | --- |
| Conversation 1 | 20.9 | 46.65 | 127,934 | 0.665 | PASS / PASS |
| Conversation 2 | 9.7 | 21.95 | 127,936 | 22.813 | PASS / PASS |

### Cold primes and three paired rounds

| Cold prime | Prompt tokens / reused | Prompt read, seconds | Engine decode tok/s |
| --- | --- | ---: | ---: |
| Conversation 1 | 127,941 / 0 | 70.00 | 56.6 |
| Conversation 2 | 127,943 / 0 | 73.51 | 58.1 |

### Cold primes and three paired rounds

| Round | Decode tok/s, 1 / 2 | TTFT seconds, 1 / 2 | Reused tokens, 1 / 2 | Wall aggregate tok/s | Largest SSE gap, 1 / 2 |
| --- | --- | --- | --- | ---: | --- |
| 1 | 33.7 / 27.4 | 7.38 / 3.77 | 127934 / 127936 | 44.78 | 0.386 / 3.492 s |
| 2 | 26.8 / 33.7 | 2.31 / 7.44 | 127934 / 127936 | 43.74 | 3.927 / 0.854 s |
| 3 | 36.6 / 5.7 | 78.35 / 2.72 | **0** / 127936 | 11.01 | 0.728 / **75.467 s** |

### Third cold read

| Existing stream | Observed SSE emission during estimated prompt read |
| --- | --- |
| Conversation 1 | Already finished; no remaining decode interval |
| Conversation 2 | **0 emitted tokens over 102.43 seconds**, approximately 0 tok/s |

### Sustained continuation leg

| Pair | Engine decode tok/s, 1 / 2 | TTFT seconds, 1 / 2 | Reused tokens, 1 / 2 | Wall aggregate tok/s | Largest gap, 1 / 2 |
| --- | --- | --- | --- | ---: | --- |
| 1 | 28.1 / 4.2 | 110.11 / 3.97 | **0** / 127936 | 7.95 | 0.651 / **105.181 s** |
| 2 | 22.3 / 29.9 | 3.55 / 9.61 | 127934 / 127936 | 36.38 | 5.770 / 1.498 s |
| 3 | 22.5 / 31.2 | 4.24 / 10.39 | 127934 / 127936 | 35.90 | 6.310 / 1.852 s |
| 4 | 32.3 / 4.0 | 115.77 / 3.57 | **0** / 127936 | 7.68 | 1.872 / **112.040 s** |

### Host states and final verdict

| Leg | Before memcpy, GB/s | After memcpy, GB/s | State evidence |
| --- | --- | --- | --- |
| TP B0 | 9.76, 9.38, 9.71 | 3.46, 3.45, 3.48 | FAST to SLOW |
| TP B1 | 3.48, 3.48, 3.57 | 2.97, 2.93, 2.95 | SLOW at both ends |
| Failed R2 launch in B | 2.94, 2.94, 2.93 | 3.69, 3.69, 3.69 | No inference; not speed evidence |
| Native R2 C | 9.46, 9.55, 9.81 | 3.10, 3.43, 3.33 | FAST to SLOW, with a completed sustained leg |

### Host states and final verdict

| Requested case | Measured evidence | Verdict |
| --- | --- | --- |
| One stream, FAST | TP A0 57.9 cold / 87.6 warm, FAST at both ends. R2's FAST-start cold primes 56.6 / 58.1; supplied prior FAST warm reference 88–99.5. | Close decode speed; **no demonstrated TP advantage**. Native's first cold prompt read was shorter. The single-warm R2 FAST comparison remains a prior reference. |
| Two streams, FAST | Matched first pair: TP 13.69 versus R2 44.78 wall tok/s, identical inputs and outputs. Both runs started FAST and ended SLOW; pair states were not individually probed. | **R2 wins the observed warm pair**, but a strictly FAST-only paired ranking is unmeasured. |
| One stream, SLOW | TP B1 cold 36.1 with SLOW at both ends; A2 late warm 41.1 before SLOW end probes. No isolated same-prompt single-warm Native SLOW leg. | **State-matched single-stream winner unresolved**. The supplied prior native ~26 per stream uses a different protocol and cannot prove TP faster here. |
| Two streams, SLOW / late load | Fully cached late native pairs 36.38 / 35.90 wall tok/s; miss-affected native leg 12.84 overall. TP's sole late pair was 13.69; TP sustained test incomplete. | **Native is the stronger measured warm baseline; neither tested recipe passes the complete two-conversation case.** Native fails retention and cold-read fairness; TP lacks the required repeated/sustained/fairness qualification. |

### Restoration, validation and evidence

| Window | Production stop marker, UTC | Verified restoration, UTC | Downtime | Restore calls |
| --- | --- | --- | --- | ---: |
| A | 11:38:39 | 12:01:43 | 23m04s | 1 |
| B | 12:02:57 | 12:26:15 | 23m17s | 1 |
| C, separately authorized native only | 12:41:02 | 12:59:14 | 18m11s | 1 |
