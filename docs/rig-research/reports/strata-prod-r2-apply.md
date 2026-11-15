# Strata prod r2 apply

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Production application, 15 November 2026, 15:45–15:52 UTC. R2 two-stream/256k was installed; switching to four-stream/128k and back passed live identity, metrics, memory-floor and two-output checks. Both installed modes used 64 GiB and sixteen parked entries. Twelve entries had been load-tested; sixteen was not separately load-tested. A 32k continuation reused 32768 positions before and after switching back. Rollback was syntax-checked and its prerequisites inspected, but it was not executed. The temporary restore guard exited after verification. No reboot/autostart qualification is established.

## Retained tables

### What changed

| Item | Before | After |
| --- | --- | --- |
| Engine | 0.1.56 (exe sha256 `21cb8dd0…2788`) | 0.1.59 (patch 1) R2 (exe sha256 `4f7ad93a13360398b0f97c7161c4b779c7125217e63f77a0abc0fde04add9c66`) |
| `start.sh` | sha256 `3701dbc6…357b` | sha256 `a8eb95d656ebc072b17376fde0f317adb765563f9e896373b04a7fde3c5e943c` (reads `recipe.current`) |
| Mode | 2 streams x 256k, 4 cache slots / 8192 MiB | recipe `2x256k`: 2 x 256k, 16 cache slots / 65536 MiB |
| Port / proxy / model / access | 18080, proxy 18081, same model + pack, local | unchanged |

## Transcribed live verification

The following checks are transcribed from the source report's numbered results, not a new run.

| Stage | Active slots / maximum context | Cache MiB / entries | Free GPU 0 / 1 MiB | Result |
| --- | --- | --- | --- | --- |
| Initial R2 apply | 2 / 262144 | 65536 / 16 | 1188 / 1038 | Identity, metrics and two-output request passed |
| Switch to four-stream mode | 4 / 131072 | 65536 / 16 | 1192 / 1148 | Same checks; 828 MiB later-card reserve present |
| Switch back | 2 / 262144 | 65536 / 16 | 1188 / 1036 | Same checks and 32k cache reuse passed |

The ~32k check used a cold prime of 33044 positions (19.7 s), then a continuation of 33045 positions: 32768 reused, 277 newly read, about 2.7 s. The same reuse check passed after switching back. Kernel checks found no Xid/ECC lines during application. This was short-prefix verification, not a long-context or unattended load qualification. Startup/free-memory samples are not load minima.
