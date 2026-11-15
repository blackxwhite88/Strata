# Strata r2 x4

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Four live slots, 131072 maximum context, 64 GiB cache and twelve entries. All twenty continuations retained their prefixes, including the final check of all four. Twelve entries filled and four evictions occurred; peak cache use was 28.38 GiB. Sixteen entries is an untested suggestion. Four-stream whole-request throughput was 52.3/53.5 early and 28.7 later. Before/after state probes cannot locate the transition.

## Retained tables

### Hurdles (what stands in the way of 4 x 128k, all cached)

| Hurdle | What I measured | Verdict |
|---|---|---|
| Cache slots | 12 of 12 used from the all-four rotation to the end; 4 evictions; 36 parks, 17 restores | **Real.** 12 has zero headroom. 16 would give one spare entry per conversation (not tested). |
| Cache bytes | Peak 28.38 GiB, final 28.15 GiB, of 65,536 MiB. About 7.0 GiB per conversation (X3 estimated 6.5). | Not a limit. 40 GiB would also have held it. |
| Host RAM | `MemAvailable` went 172 GiB (after launch) to 143 GiB (end). Engine floor `conversation_cache_min_free_mib` is 2560. | Not a limit. |
| VRAM | Floor 494 / 440 MiB with `vram-reserve-later-mib=828` copied from the earlier four-slot window. | Holds, but small margin. Do not drop the 828. |
| Context ceiling | Max context is 131,072 per stream. A conversation here is 128.5k prompt + 512 reply = 129.05k. | **Real.** About 2k tokens of room: a conversation that grows past about 131k stops fitting. This setup gives up the 256k context production has today. |
| Cold read | Not measured here (no cold read ran while a stream was decoding). Earlier evidence: a cold 128k read freezes a decoding stream 73 to 88 s, and R3 (reading while decoding) gives non-finite logits and is not usable. | **Real for any loss.** One lost conversation costs 70 to 110 s and stalls the others. |
| Speed | Aggregate 52 to 54 tok/s (FAST host), 29 tok/s later; per stream 7.5 to 21.5. The launch plan itself warns that 4 requests at once is more than a 22 GB card usually holds (it fits 2), so answers are slower. | Usable, but not fast. About 4 x 128k streams are slower than 2 x 256k per stream. |
| Time to first token when cached | 2.3 to 19.6 s even with a full cache hit (four continuations queue for restore and a 600-token read). | Visible but small next to a cold read. |
| Test length | About 9.5 minutes under load. | A longer run will churn the cache more (evictions were already rising). |

### Host memcpy probes (GB/s; FAST is 9 or more, SLOW 4.5 or less)

| When | Samples | State |
|---|---|---|
| Before | 9.33, 9.47, 9.69 | FAST |
| After | 3.84, 3.84, 3.79 | SLOW |

### Four-stream speed

| Group | Order | Streams | Tokens each | Per-stream decode tok/s | Wall aggregate tok/s | cache_n all above 120,000 |
|---|---|---|---|---|---|---|
| round1 | [1, 2, 3, 4] | 4 | 512 | 19.8, 16.3, 17.8, 14.6 | 52.3 | True |
| round2 | [1, 2, 3, 4] | 4 | 512 | 18.3, 14.5, 21.5, 15.9 | 53.5 | True |
| rotA | [3, 1] | 2 | 256 | 18.4, 28.1 | 31.6 | True |
| rotB | [4, 2] | 2 | 256 | 21.8, 16.5 | 28.0 | True |
| rotAll | [4, 3, 2, 1] | 4 | 512 | 8.9, 8.1, 7.5, 9.9 | 28.7 | True |
| loss | [4, 3, 2, 1] | 4 | 128 | 13.2, 6.3, 8.5, 5.0 | 18.0 | True |

### What filled the cache

| After | Parked entries | GiB | Evictions | Parks | Restores | Host MemAvailable GiB |
|---|---|---|---|---|---|---|
| after-launch | 0 | 0.00 | 0 | 0 | 0 | 172 |
| after-prime1 | 1 | 0.22 | 0 | 1 | 0 | 171 |
| after-prime2 | 2 | 2.82 | 0 | 2 | 0 | 169 |
| after-prime3 | 3 | 5.43 | 0 | 3 | 0 | 166 |
| after-prime4 | 4 | 8.03 | 0 | 4 | 0 | 163 |
| after-round1 | 4 | 10.09 | 0 | 8 | 3 | 161 |
| after-round2 | 7 | 16.49 | 0 | 15 | 7 | 155 |
| after-rotA | 8 | 18.43 | 0 | 18 | 8 | 153 |
| after-rotB | 9 | 20.49 | 0 | 21 | 10 | 151 |
| after-rotAll | 12 | 28.38 | 1 | 29 | 14 | 143 |
| after-loss | 12 | 28.15 | 4 | 36 | 17 | 143 |
| after-loss-check | 12 | 28.15 | 4 | 36 | 17 | 143 |
| end | 12 | 28.15 | 4 | 36 | 17 | 143 |

### Per-request results

| Step | Conv | cache_n | Fresh prompt tokens | TTFT s | Decode tok/s | Largest gap s |
|---|---|---|---|---|---|---|
| Prime (cold, 512 tok) | 1 | 0 | 127941 | 70.4 | 58.3 | 0.1 |
| Prime (cold, 512 tok) | 2 | 0 | 127943 | 73.9 | 57.6 | 0.0 |
| Prime (cold, 512 tok) | 3 | 0 | 127943 | 74.7 | 58.7 | 0.1 |
| Prime (cold, 512 tok) | 4 | 0 | 127943 | 75.0 | 59.2 | 0.0 |
| round1 (512 tok) | 1 | 127934 | 601 | 13.4 | 19.8 | 0.4 |
| round1 (512 tok) | 2 | 127936 | 601 | 7.5 | 16.3 | 2.9 |
| round1 (512 tok) | 3 | 127936 | 601 | 10.4 | 17.8 | 2.9 |
| round1 (512 tok) | 4 | 127936 | 601 | 3.9 | 14.6 | 3.5 |
| round2 (512 tok) | 1 | 127934 | 601 | 10.4 | 18.3 | 4.4 |
| round2 (512 tok) | 2 | 127936 | 601 | 2.8 | 14.5 | 4.5 |
| round2 (512 tok) | 3 | 127936 | 601 | 14.5 | 21.5 | 1.9 |
| round2 (512 tok) | 4 | 127936 | 601 | 6.0 | 15.9 | 4.4 |
| rotA (256 tok) | 3 | 127936 | 601 | 2.3 | 18.4 | 6.1 |
| rotA (256 tok) | 1 | 127934 | 601 | 7.2 | 28.1 | 1.9 |
| rotB (256 tok) | 4 | 127936 | 601 | 6.6 | 21.8 | 2.4 |
| rotB (256 tok) | 2 | 127936 | 601 | 2.6 | 16.5 | 5.9 |
| rotAll (512 tok) | 4 | 127936 | 601 | 13.6 | 8.9 | 6.1 |
| rotAll (512 tok) | 3 | 127936 | 601 | 8.4 | 8.1 | 6.0 |
| rotAll (512 tok) | 2 | 127936 | 601 | 2.8 | 7.5 | 6.1 |
| rotAll (512 tok) | 1 | 127934 | 601 | 19.6 | 9.9 | 2.4 |
| loss (128 tok) | 4 | 127936 | 600 | 18.7 | 13.2 | 1.8 |
| loss (128 tok) | 3 | 127936 | 600 | 8.0 | 6.3 | 5.4 |
| loss (128 tok) | 2 | 127936 | 600 | 13.4 | 8.5 | 5.4 |
| loss (128 tok) | 1 | 127934 | 600 | 2.9 | 5.0 | 6.2 |
