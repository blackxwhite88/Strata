#!/usr/bin/env python3
"""Request-only timing adapter derived from the final cache-window request/group code.

Reads newly supplied synthetic message lists. Writes numeric timings and digests,
never message or generated text. Does not start, stop or restore any service.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import time
import urllib.request
import uuid


def request(base_url, model, messages, count, seed, timeout, label):
    payload = dict(
        model=model, messages=messages, temperature=0, max_tokens=count,
        seed=seed, stream=True, stream_options={"include_usage": True},
        stop=["<|im_end|>", "<|endoftext|>"], reasoning_effort="none",
        chat_template_kwargs={"enable_thinking": False},
    )
    headers = {"Content-Type": "application/json"}
    access_key = os.environ.get("RIG_API_KEY")
    if access_key:
        headers["Authorization"] = "Bearer " + access_key
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(), headers=headers,
    )
    start = time.monotonic()
    events, pieces, usage, timings = [], [], {}, {}
    done = False
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            if time.monotonic() - start > timeout:
                raise RuntimeError("request deadline exceeded")
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            if line[5:].strip() == "[DONE]":
                done = True
                break
            data = json.loads(line[5:])
            if data.get("error"):
                raise RuntimeError("server stream returned an error")
            usage = data.get("usage") or usage
            timings = data.get("timings") or timings
            for choice in data.get("choices", []):
                delta = choice.get("delta", {})
                part = "".join(delta.get(k, "") or "" for k in
                               ("content", "reasoning_content", "reasoning"))
                if part:
                    events.append(time.monotonic())
                    pieces.append(part)
    end = time.monotonic()
    if not done or usage.get("completion_tokens") != count or len(events) < 2:
        raise RuntimeError("incomplete stream, output length mismatch or insufficient timing events")
    span = events[-1] - events[0]
    if span <= 0:
        raise RuntimeError("invalid emission interval")
    # Keep an explicit numeric allowlist; servers can add arbitrary metadata.
    engine_fields = ("cache_n", "prompt_n", "prompt_ms", "prompt_per_second",
                     "predicted_per_second", "predicted_ms", "predicted_n")
    if any(isinstance(timings.get(k), (int, float)) and not math.isfinite(timings[k])
           for k in engine_fields):
        raise RuntimeError("non-finite engine timing")
    safe_timings = {k: timings[k] for k in engine_fields
                    if isinstance(timings.get(k), (int, float))}
    return dict(
        label=label, send=start, end=end, first=events[0], last=events[-1],
        events=events, completion_tokens=count, timings=safe_timings,
        ttft_s=events[0] - start, decode_tok_s=(count - 1) / span,
        largest_gap_s=max(b - a for a, b in zip(events, events[1:])),
        input_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
        output_sha256=hashlib.sha256("".join(pieces).encode()).hexdigest(),
    )


def group(args, histories, tag, nonce, warm):
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(histories)) as pool:
        futures = []
        for i, history in enumerate(histories):
            messages = history + ([{"role": "user", "content":
                f"Synthetic continuation {nonce}-{tag}-{i}. Continue the inventory "
                "with numbered entries until the output limit."}] if warm else [])
            futures.append(pool.submit(request, args.base_url, args.model, messages,
                                       args.outputs, args.seed, args.timeout, f"{tag}-{i}"))
        for future in futures:
            rows.append(future.result())
    qualified = not warm or all(
        r["timings"].get("cache_n", 0) >= args.min_cache_n for r in rows)
    wall = max(r["end"] for r in rows) - min(r["send"] for r in rows)
    return dict(label=tag, qualified=qualified, rows=rows, wall_s=wall,
                wall_tok_s=sum(r["completion_tokens"] for r in rows) / wall,
                decode_sum_tok_s=sum(r["decode_tok_s"] for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Local API base ending in /v1")
    parser.add_argument("--model", default="qwen3.8")
    parser.add_argument("--messages", type=Path, nargs="+", required=True,
                        help="New synthetic JSON message lists, one per independent history")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outputs", type=int, default=512)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=40261114)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--min-cache-n", type=int, default=1)
    args = parser.parse_args()
    if args.outputs < 512 or args.rounds < 1 or args.timeout <= 0 or args.min_cache_n < 1:
        parser.error("require outputs >=512, rounds >=1, timeout >0 and min-cache-n >=1")
    # The network destination must be supplied explicitly. It is not persisted.
    if not args.base_url.startswith(("http://", "https://")):
        parser.error("base-url must use HTTP or HTTPS")
    histories, hashes = [], set()
    for path in args.messages:
        history = json.loads(path.read_text())
        if not isinstance(history, list) or not history or any(
            not isinstance(m, dict) or not isinstance(m.get("content"), str)
            or m.get("role") not in ("system", "user", "assistant") for m in history
        ):
            parser.error("each input must be a nonempty synthetic text message list")
        key = hashlib.sha256(json.dumps(history, sort_keys=True).encode()).hexdigest()
        if key in hashes:
            parser.error("independent histories must differ near their first user content")
        hashes.add(key)
        histories.append(history)
    result = dict(seed=args.seed, nonce=uuid.uuid4().hex, temperature=0,
                  outputs=args.outputs, groups=[], status="running",
                  metric="client SSE emission timing; not a hardware profiler")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")

    save()
    try:
        # Cold primes run sequentially to avoid conflating slot admission and read time.
        for i, history in enumerate(histories):
            result["groups"].append(group(args, [history], f"prime-{i}", result["nonce"], False))
            save()
        for r in range(args.rounds):
            measured = group(args, histories, f"round-{r + 1}", result["nonce"], True)
            result["groups"].append(measured)
            save()
            if not measured["qualified"]:
                raise RuntimeError("warm-prefix reuse assertion failed")
        result["status"] = "passed request lengths and warm-prefix threshold"
        save()
    except Exception:
        # Avoid copying a remote error body, input path, endpoint or generated text.
        result["status"] = "failed; inspect the local service privately before another run"
        save()
        raise SystemExit("measurement failed; numeric partial results saved") from None
    print(json.dumps({"status": result["status"], "groups": len(result["groups"])}))


if __name__ == "__main__":
    main()
