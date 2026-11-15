# Strata tp speed

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Opt-in TP speed implementation on a separate development branch. The implementation report alone contains no measured speedup. Later final windows measured copy counters, copy-engine staging and prefetch. No engine source is included in this documentation bundle.

## Retained tables

### Flags

| Switch | Effect when enabled | Limits |
| --- | --- | --- |
| `FNX_CACHE_PREFETCH=1` | Guess the next layer's experts with the existing probe router and stage only guessed misses during the current layer's MoE compute. Print a per-card summary at engine destruction. | Requires `FNX_CACHE_COPY_ENGINE=1`. Alone it prints a disabled message. Staging allocation failure disables prefetch and retains demand DMA. |
| `FNX_CACHE_COPY_STATS=1` | Print per-window, per-card host bytes copied and time spent in the copy-wait interval. Works independently with the original SM path. | CUDA timer only. Adds two timing kernels per cached layer and a counter download per window. |
| `FNX_READ_INTERLEAVE=1` | During another lane's prompt read, use smaller prompt slices and run a bounded number of decode windows between slices. | Server path. Only changes reads that begin while another lane is decoding or paused. |

### Flags

| Knob | Enabled default | Validation |
| --- | --- | --- |
| `FNX_READ_CHUNK_ROWS` | `2048` | 256 through 8192, a multiple of 256. A chunk cannot exceed the allocated prompt chunk size. |
| `FNX_READ_DECODE_TOKENS` | `8` | Target new tokens for each eligible decoding lane between prompt slices. |
| `FNX_READ_DECODE_WINDOWS` | `8` | Hard window cap per slice. Require `1 <= tokens <= windows <= 256`. |
