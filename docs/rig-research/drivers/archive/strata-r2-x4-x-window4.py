# Sanitized archival driver; original lifecycle code is retained for inspection.
# Local installation paths/endpoints and synthetic inputs have been omitted.
# This file is deliberately disabled, including when imported.
raise RuntimeError("Archive only: adapt paths, fixtures, ownership and restoration before use.")

import re
import concurrent.futures as cf
import hashlib, json, os, pathlib, signal, subprocess, sys, threading, time, traceback, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent
MODE = sys.argv[1]
E = ROOT / ('evidence-' + MODE)
MAXMIN = 26
HARDMIN = 30
NO_NEW_CANDIDATE_MIN = 24
SUSTAIN_S = 180
SLOTS = 12
LIVE = 4
CTX_TOKENS = 131072
RESERVE_LATER = 828
ROTATION_TOKENS = 256
LOSS_TOKENS = 128
PHASE_MIN = 24
LOSS_CHECK_RESERVE_S = 240
HOME = pathlib.Path.home()
DIGEST = '3701dbc6ffcfee6cf09cd918e8bf1c7145fc492216bcf9f3d16d08973ff4357b'
NATIVE_SHA = '4f7ad93a13360398b0f97c7161c4b779c7125217e63f77a0abc0fde04add9c66'
CACHE_MIB = 65536
CUDA13 = str(HOME / 'benchmark/cuda-13.3/lib')
GGUF = HOME / '<model path>'
START = None
PHASE_DEADLINE = None

def save(name, data):
    p = E / name
    q = p.with_suffix(p.suffix + '.tmp')
    q.write_text(json.dumps(data, indent=2))
    q.replace(p)

def event(kind, **kw):
    with (E / 'events.jsonl').open('a') as f:
        f.write(json.dumps({'time': time.time(), 'kind': kind, **kw}) + '\n')
    print(kind, kw, flush=True)

def call(args, timeout=15):
    p = subprocess.run([str(x) for x in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return (p.returncode, p.stdout)

def call_env(args, env, timeout):
    p = subprocess.run([str(x) for x in args], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return (p.returncode, p.stdout)

def digest():
    return hashlib.sha256((HOME / 'production/start.sh').read_bytes()).hexdigest()

def ident(pid):
    try:
        return pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()[19]
    except FileNotFoundError:
        return None

def owned(record):
    return ident(record['pid']) == record['start']

def engine_pids(runtime_dir=None):
    out = []
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = proc.joinpath('cmdline').read_bytes().decode().strip('\x00').split('\x00')
            if '--native' not in args or '--serve' not in args:
                continue
            if runtime_dir is not None:
                env = dict((s.split('=', 1) for s in proc.joinpath('environ').read_bytes().decode().strip('\x00').split('\x00') if '=' in s))
                if env.get('STRATA_RUNTIME_DIR') != runtime_dir:
                    continue
            out.append(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return out

def candidate_stop():
    ns = E / 'native-namespace.json'
    if ns.exists():
        namespace = json.loads(ns.read_text())
        env = os.environ.copy()
        env.update(namespace)
        try:
            rc, out = call_env([HOME / 'benchmark/bin/strata', 'launch', '--stop'], env, 60)
            (E / 'native-stop.log').write_text(out)
        except BaseException as exc:
            (E / 'native-stop.log').write_text('stop failed ' + repr(exc))
        until = time.monotonic() + 30
        rd = namespace['STRATA_RUNTIME_DIR']
        while engine_pids(rd) and time.monotonic() < until:
            time.sleep(0.5)
        for pid in engine_pids(rd):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        until = time.monotonic() + 15
        while engine_pids(rd) and time.monotonic() < until:
            time.sleep(0.5)
        for pid in engine_pids(rd):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

def api(path='/v1/models', port=18082, payload=None, timeout=10):
    req = urllib.request.Request(f'http://<local endpoint>:{port}' + path, data=json.dumps(payload).encode() if payload else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def restore(reason):
    try:
        (E / 'restore.claim').mkdir()
    except FileExistsError:
        return
    event('restore-start', reason=reason)
    candidate_stop()
    before = digest()
    if before != DIGEST:
        raise RuntimeError('launcher digest changed before restoration')
    rc, out = call(['bash', HOME / 'production/start.sh'], 240)
    (E / 'restore-start.log').write_text(out)
    qrc, q = call(['systemctl', '--user', 'is-active', 'gpu0-quarantine.service'])
    chat = api('/v1/chat/completions', 18081, {'model': 'qwen3.8', 'messages': [{'role': 'user', 'content': '<synthetic input omitted>'}], 'max_tokens': 2, 'temperature': 0, 'stream': False, 'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False}}, 120)
    save('restore-chat.json', chat)
    result = dict(time=time.time(), reason=reason, start_rc=rc, before=before, after=digest(), quarantine=q.strip(), completion_tokens=chat.get('usage', {}).get('completion_tokens'))
    result['ok'] = rc == 0 and before == digest() == DIGEST and (qrc == 0) and (result['completion_tokens'] == 2)
    save('restore-validation.json', result)
    event('restored', **result)

def health(since):
    rc, q = call(['systemctl', '--user', 'is-active', 'gpu0-quarantine.service'])
    if rc:
        raise RuntimeError('quarantine inactive ' + q)
    rc, j = call(['journalctl', '-k', '--since', f'<time selector>{since}', '--no-pager', '-g', 'NVRM: Xid|XID|uncorrect.*ECC'])
    no_entries = 'No entries' in j
    access_problem = any((s in j.lower() for s in ['permission', 'not seeing', 'insufficient']))
    if rc and (not (rc == 1 and no_entries)) or access_problem:
        raise RuntimeError('kernel log unavailable ' + j)
    if j.strip() and 'No entries' not in j:
        (E / 'hardware-abort.log').write_text(j)
        raise RuntimeError('Xid/ECC ' + j[-1800:])
    rc, g = call(['nvidia-smi', '--query-gpu=index,temperature.gpu,memory.free,ecc.errors.uncorrected.volatile.total', '--format=csv,noheader,nounits'])
    if rc:
        raise RuntimeError('GPU query failed ' + g)
    for row in g.splitlines():
        p = [s.strip() for s in row.split(',')]
        if float(p[1]) > 85 or (p[3].isdigit() and int(p[3]) > 0):
            raise RuntimeError('GPU thermal/ECC ' + row)
    active = E / 'active-log.json'
    logs = list(E.glob('*.engine.log'))
    if active.exists():
        p = pathlib.Path(json.loads(active.read_text()))
        if p.exists() and p not in logs:
            logs.append(p)
    for log in logs:
        tail = log.read_text(errors='replace')[-12000:]
        if re.search('non[- ]?finite|CUDA error|cudaError|ring.*(?:invalid|error)', tail, re.I):
            raise RuntimeError('fatal engine diagnostic ' + log.name + ' ' + tail[-1500:])
    with (E / 'health.jsonl').open('a') as f:
        f.write(json.dumps({'time': time.time(), 'gpu': g.strip()}) + '\n')

def start_health_monitor(since):

    def monitor():
        while not (E / 'restore-validation.json').exists():
            if (E / 'production-down').exists():
                try:
                    health(since)
                except BaseException as exc:
                    save('guard-health-abort.json', dict(reason=repr(exc), time=time.time()))
                    return
            time.sleep(1)
    threading.Thread(target=monitor, daemon=True).start()

def guard():
    state = json.loads((E / 'window.json').read_text())
    save('guard-armed.json', dict(pid=os.getpid(), **state))
    start_health_monitor(state['start'])
    while not (E / 'restore-validation.json').exists():
        reason = None
        try:
            now = time.time()
            if (E / 'production-down').exists():
                if now >= state['hard_stop']:
                    reason = 'window hard restore deadline'
                elif now >= state['test_deadline']:
                    reason = 'window maximum test budget; restore now'
                elif (E / 'guard-health-abort.json').exists():
                    reason = 'guard safety abort: ' + json.loads((E / 'guard-health-abort.json').read_text())['reason']
                elif not owned(state['driver']):
                    reason = 'driver lost'
                elif (E / 'finish.json').exists():
                    reason = json.loads((E / 'finish.json').read_text())['reason']
            elif not owned(state['driver']):
                return
        except BaseException as exc:
            reason = 'guard safety abort: ' + repr(exc)
        if reason:
            save('guard-abort.json', dict(time=time.time(), reason=reason))
            driver = state['driver']
            if not (E / 'finish.json').exists() and owned(driver):
                try:
                    os.kill(driver['pid'], signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                restore(reason)
            except BaseException as exc:
                save('restore-failed.json', dict(time=time.time(), error=repr(exc)))
                traceback.print_exc()
            return
        time.sleep(1)
STOP = threading.Event()

class BudgetError(RuntimeError):
    pass

class FloorError(RuntimeError):
    pass

def request(messages, limit, label, on_first=None):
    payload = dict(model='qwen3.8', messages=messages, temperature=0, max_tokens=limit, seed=40261114, stream=True, stream_options={'include_usage': True}, stop=['<|im_end|>', '<|endoftext|>'], reasoning_effort='none', chat_template_kwargs={'enable_thinking': False})
    save(label + '.input.json', payload)
    req = urllib.request.Request('http://<local endpoint>:18082/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    assert time.time() < PHASE_DEADLINE, 'no request after the phase deadline'
    active = E / 'active-log.json'
    logpath = pathlib.Path(json.loads(active.read_text())) if active.exists() else None
    log_start = logpath.stat().st_size if logpath and logpath.exists() else None
    start = time.monotonic()
    events = []
    event_lengths = []
    usage = {}
    timings = {}
    text = ''
    try:
        with urllib.request.urlopen(req, timeout=360) as response:
            for raw in response:
                if STOP.is_set():
                    raise RuntimeError('phase already failed or censored')
                line = raw.decode().strip()
                if not line.startswith('data:') or line[5:].strip() == '[DONE]':
                    continue
                data = json.loads(line[5:])
                if data.get('error'):
                    raise RuntimeError('server stream error: ' + str(data['error']))
                if data.get('usage'):
                    usage = data['usage']
                if data.get('timings'):
                    timings = data['timings']
                for choice in data.get('choices', []):
                    delta = choice.get('delta', {})
                    s = ''.join((delta.get(k, '') or '' for k in ['content', 'reasoning_content', 'reasoning']))
                    if s:
                        now = time.monotonic()
                        events.append(now)
                        text += s
                        event_lengths.append(len(text))
                        if on_first is not None:
                            on_first.set()
        result = dict(label=label, send=start, end=time.monotonic(), first=events[0] if events else None, last=events[-1] if events else None, fragments=len(events), events=events, event_lengths=event_lengths, engine_log_start=log_start, engine_log_end=logpath.stat().st_size if logpath and logpath.exists() else None, usage=usage, timings=timings, text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
        save(label + '.result.json', result)
        if usage.get('completion_tokens') != limit:
            raise RuntimeError('completion length ' + str(usage))
        return result
    except BaseException as exc:
        save(label + '.error.json', dict(error=repr(exc), usage=usage, timings=timings, fragments=len(events), partial_text=text[-2000:], events=events, event_lengths=event_lengths, send=start, end=time.monotonic(), engine_log_start=log_start))
        STOP.set()
        raise

def start_native(name, piped_concurrent):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('FNX_', 'STRATA_'))}
    namespace = {'XDG_STATE_HOME': str(ROOT / (name + '.state')), 'STRATA_PROFILE_DIR': str(ROOT / (name + '.profiles')), 'STRATA_RUNTIME_DIR': str(ROOT / (name + '.runtime'))}
    env.update(namespace)
    save('native-namespace.json', namespace)
    env['LD_LIBRARY_PATH'] = CUDA13 + ':' + env.get('LD_LIBRARY_PATH', '')
    save(name + '.runtime-path.json', dict(prefix=CUDA13))
    logpath = pathlib.Path(namespace['XDG_STATE_HOME']) / 'strata/launch/ud-iq4_xs-128k.engine.log'
    save('active-log.json', str(logpath))
    args = [HOME / 'benchmark/bin/strata', 'launch', '--model-path', GGUF, '--model', 'ud-iq4_xs', '--family', 'unsloth', '--data-dir', HOME / '<model path>', '--context', '128k', '--kv', 'int8', '--vision', 'on', '--parallel', '4', '--drafting', 'mtp', '--access', 'local', '--port', '18082', '--tune', 'skip', '--yes', '--no-tui', '--split-engine', 'off']
    settings = ['STRATA_BF16_TC=1', 'STRATA_GDN_CONVL2=2', 'spec=3', 'pipeline_windows=1', 'STRATA_PF_GROUP_SCRATCH=1', 'STRATA_PF_HC_REGION=1', 'layer-split=23', 'trim-stage-weights=1', 'STRATA_STAGE_TRIM=1', 'batch-mtp=1', 'STRATA_PIPED_MTP=1', 'STRATA_BATCH_SELF_COMMIT=0', 'STRATA_PIPED_CONCURRENT=' + ('1' if piped_concurrent else '0'), 'STRATA_SM75_PERF=0', 'prefill-pipe=0', 'vram-reserve-later-mib=%d' % RESERVE_LATER, 'conversation-cache-mib=%d' % CACHE_MIB, 'conversation-cache-slots=%d' % SLOTS]
    for s in settings:
        args += ['--set', s]
    save(name + '.launch.json', dict(args=list(map(str, args)), namespace=namespace, ld_library_path_prefix=CUDA13))
    rc, out = call_env(args, env, 240)
    (E / (name + '.launch.log')).write_text(out)
    if rc:
        raise RuntimeError('launch failed ' + out[-1000:])
    api()
    return logpath

def vram_floor(name, when):
    rc, g = call(['nvidia-smi', '--query-gpu=index,memory.free,memory.used', '--format=csv,noheader,nounits'])
    rows = [dict(zip(('gpu', 'free_mib', 'used_mib'), [int(x) for x in row.split(',')])) for row in g.strip().splitlines()] if rc == 0 else []
    with (E / (name + '.vram.jsonl')).open('a') as f:
        f.write(json.dumps(dict(time=time.time(), when=when, rc=rc, gpus=rows)) + '\n')
    if rc or len(rows) != 2 or any((r['free_mib'] < 300 for r in rows)):
        raise FloorError('VRAM floor 300 MiB failed at ' + when + ': ' + g.strip())

def live_cache():
    m = api('/metrics', timeout=10)
    return dict(conversation_cache=m.get('conversation_cache'), engine_conversation_cache_mib=m.get('engine', {}).get('conversation_cache_mib'), engine_conversation_cache_slots=m.get('engine', {}).get('conversation_cache_slots'))
TRACE = []

def meminfo():
    for ln in pathlib.Path('/proc/meminfo').read_text().splitlines():
        if ln.startswith('MemAvailable:'):
            return int(ln.split()[1]) // 1024

def snap(name, when):
    try:
        row = dict(time=time.time(), when=when, mem_available_mib=meminfo(), **live_cache())
    except BaseException as exc:
        row = dict(time=time.time(), when=when, error=repr(exc))
    TRACE.append(row)
    save(name + '.cache-trace.json', TRACE)
    return row

def identity(name, piped_concurrent):
    actual = []
    for pid in engine_pids():
        proc = pathlib.Path('/proc') / str(pid)
        try:
            args = proc.joinpath('cmdline').read_bytes().decode().strip('\x00').split('\x00')
            exe = os.readlink(proc / 'exe')
            env = dict((s.split('=', 1) for s in proc.joinpath('environ').read_bytes().decode().strip('\x00').split('\x00') if '=' in s))
            actual.append(dict(pid=pid, args=args, exe=exe, sha256=hashlib.sha256(pathlib.Path(exe).read_bytes()).hexdigest(), env={k: v for k, v in env.items() if k.startswith(('FNX_', 'STRATA_', 'LD_LIBRARY')) and (not re.search('KEY|TOKEN|SECRET|PASSWORD', k))}))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    save(name + '.actual-process.json', actual)
    assert len(actual) == 1, 'expected one model engine; no overlap'
    r = actual[0]
    args = r['args']
    env = r['env']
    assert r['sha256'] == NATIVE_SHA, 'engine hash'

    def arg(k):
        return args[args.index(k) + 1]
    assert arg('--batch') == str(LIVE) and arg('--max-context') == str(CTX_TOKENS) and (arg('--spec') == '3') and (arg('--vram-reserve-later-mib') == str(RESERVE_LATER))
    assert arg('--layer-split') == '23' and arg('--kv') == 'int8' and ('--vision' in args) and (arg('--kv-resident') == '32768')
    assert '--trim-stage-weights' in args and '--batch-mtp' in args
    assert env.get('STRATA_STAGE_TRIM') == '1' and env.get('STRATA_PIPED_MTP') == '1' and (env.get('STRATA_BATCH_SELF_COMMIT') == '0')
    assert env.get('STRATA_PIPED_CONCURRENT', '0') == ('1' if piped_concurrent else '0')
    assert env.get('STRATA_SM75_PERF', '0') == '0' and ('--prefill-pipe' not in args or arg('--prefill-pipe') == '0')
    assert CUDA13 in env.get('LD_LIBRARY_PATH', '').split(':'), 'CUDA 13 runtime path missing from candidate'
    if '--conversation-cache-mib' not in args or arg('--conversation-cache-mib') != str(CACHE_MIB):
        raise BudgetError('argv does not carry --conversation-cache-mib %d: %s' % (CACHE_MIB, args))
    if '--conversation-cache-slots' not in args or arg('--conversation-cache-slots') != str(SLOTS):
        raise BudgetError('argv does not carry --conversation-cache-slots %d: %s' % (SLOTS, args))
    assert env.get('STRATA_PIPED_CONCURRENT', '0') == '0', 'concurrent prefill must be off'
    live = live_cache()
    save(name + '.live-budget.json', live)
    em = api('/metrics', timeout=10).get('engine', {})
    save(name + '.live-engine.json', em)
    if em.get('batch_slots') != LIVE:
        raise BudgetError('live decode slots are not %d: %s' % (LIVE, em.get('batch_slots')))
    cc = live.get('conversation_cache') or {}
    if cc.get('budget_mib') != CACHE_MIB or live.get('engine_conversation_cache_mib') != CACHE_MIB or (not cc.get('enabled')):
        raise BudgetError('live budget is not %d MiB: %s' % (CACHE_MIB, live))
    live_slots = [cc.get('slots'), live.get('engine_conversation_cache_slots')]
    if SLOTS not in live_slots or any((x not in (None, SLOTS) for x in live_slots)):
        raise BudgetError('live slot count is not %d: %s' % (SLOTS, live))
    vram_floor(name, 'after-launch')
    return r

def probe(phase):
    rows = []
    for i in range(3):
        health(int(START))
        start = time.time()
        rc, out = call(['python3', '-I', HOME / 'benchmark/tp-truth-transport/hostprobe.py'], 45)
        match = re.search('memcpy_GB_s=([\\d.]+)', out)
        row = dict(time=start, phase=phase, sample=i + 1, rc=rc, raw=out)
        if match:
            row['memcpy_GB_s'] = float(match[1])
            row['state'] = 'FAST' if row['memcpy_GB_s'] >= 9 else 'SLOW'
        rows.append(row)
        save('host-probe-' + phase + '.json', rows)
        if rc or not match:
            raise RuntimeError('host probe failed ' + out[-500:])
        event('host-probe', **row)
    return rows

def probe_state(rows):
    s = {r['state'] for r in rows}
    return s.pop() if len(s) == 1 else 'MIXED'
LONG = '<synthetic input omitted>'

def suffix(tag):
    raise RuntimeError('Synthetic fixtures are omitted; provide newly generated inputs.')

def summary_row(row):
    n = row['usage']['completion_tokens']
    span = row['last'] - row['first']
    t = row['timings']
    return dict(label=row['label'], n=n, prompt_n=t.get('prompt_n'), cache_n=t.get('cache_n'), prompt_ms=t.get('prompt_ms'), decode_tok_s=(n - 1) / span, engine_decode_tok_s=t.get('predicted_per_second'), ttft_s=row['first'] - row['send'], max_gap_s=max((b - a for a, b in zip(row['events'], row['events'][1:]))), wall_s=row['end'] - row['send'], marker_present='TP-TRUTH-WAREHOUSE' in row['text'])

def fixtures():
    raise RuntimeError('Synthetic fixtures are omitted; provide newly generated inputs.')

def largest_gap(ev):
    return max((b - a for a, b in zip(ev, ev[1:])), default=0.0)

def group(name, refs, order, tag, limit):
    n = len(order)
    bar = threading.Barrier(n)

    def work(c):
        messages = refs[c] + [suffix(f'Synthetic r2x4 nonce {tag}-c{c + 1}.')]
        bar.wait(timeout=10)
        return request(messages, limit, f'{name}-{tag}-conv{c + 1}')
    with cf.ThreadPoolExecutor(max_workers=n) as pool:
        fut = [pool.submit(work, c) for c in order]
        done, _ = cf.wait(fut, return_when=cf.FIRST_EXCEPTION)
        if any((f.exception() for f in done)):
            STOP.set()
        rows = [f.result() for f in fut]
    sr = []
    for c, r in zip(order, rows):
        s = summary_row(r)
        s['conversation'] = c + 1
        sr.append(s)
    out = dict(tag=tag, order=[c + 1 for c in order], limit=limit, rows=sr, wall_aggregate_tok_s=n * limit / (max((r['end'] for r in rows)) - min((r['send'] for r in rows))), per_stream_decode_tok_s=[round(s['decode_tok_s'], 1) for s in sr], cache_n=[s['cache_n'] for s in sr], ttft_s=[round(s['ttft_s'], 1) for s in sr], send_skew_s=max((r['send'] for r in rows)) - min((r['send'] for r in rows)), emission_overlap_s=min((r['last'] for r in rows)) - max((r['first'] for r in rows)))
    out['all_above_120000'] = all(((x or 0) > 120000 for x in out['cache_n']))
    save(f'{name}-{tag}.group.json', out)
    event('group-complete', phase=name, **{k: v for k, v in out.items() if k != 'rows'})
    snap(name, 'after-' + tag)
    vram_floor(name, 'after-' + tag)
    return out

def finish_engine(name, logpath):
    try:
        probe(name + '-after')
    finally:
        candidate_stop()
        if logpath and logpath.exists():
            (E / (name + '.engine.log')).write_bytes(logpath.read_bytes())
    health(int(START))

def time_left_ok(reserve_s):
    return time.time() < PHASE_DEADLINE - reserve_s

def phase(name, piped_concurrent, deadline_min):
    global PHASE_DEADLINE
    result = dict(name=name, piped_concurrent=piped_concurrent, cache_mib=CACHE_MIB, slots=SLOTS, live_slots=LIVE, start=time.time(), primes=[], groups=[], skipped=[])
    logpath = None
    fatal = None
    TRACE.clear()
    STOP.clear()
    PHASE_DEADLINE = START + min(deadline_min, PHASE_MIN) * 60
    finished = threading.Event()

    def budget_watch():
        while not finished.wait(0.25):
            if time.time() >= PHASE_DEADLINE:
                save(name + '.budget-censored.json', dict(time=time.time(), deadline=PHASE_DEADLINE))
                STOP.set()
                candidate_stop()
                return
    timer = threading.Thread(target=budget_watch, daemon=True)
    timer.start()
    try:
        before = probe(name + '-before')
        result['probe_before'] = [r['memcpy_GB_s'] for r in before]
        result['state_before'] = probe_state(before)
        logpath = start_native(name, piped_concurrent)
        save('active-log.json', str(logpath))
        result['identity'] = identity(name, piped_concurrent)
        health(int(START))
        snap(name, 'after-launch')
        result['launch_done'] = time.time()
        refs = fixtures()
        for c in range(LIVE):
            cold = request(refs[c][:1], 512, f'{name}-prime{c + 1}')
            row = summary_row(cold)
            row['conversation'] = c + 1
            result['primes'].append(row)
            assert (cold['timings'].get('cache_n') or 0) <= 32, 'independent cold prime reused a long prefix'
            snap(name, 'after-prime%d' % (c + 1))
            vram_floor(name, 'after-prime%d' % (c + 1))
            save(name + '.summary.json', result)
        allc = list(range(LIVE))
        for i in (1, 2):
            result['groups'].append(group(name, refs, allc, 'round%d' % i, 512))
            save(name + '.summary.json', result)
        if time_left_ok(LOSS_CHECK_RESERVE_S + 200):
            result['groups'].append(group(name, refs, [2, 0], 'rotA', ROTATION_TOKENS))
            save(name + '.summary.json', result)
            result['groups'].append(group(name, refs, [3, 1], 'rotB', ROTATION_TOKENS))
            save(name + '.summary.json', result)
        else:
            result['skipped'].append('rotation pairs: not enough window time')
        if time_left_ok(LOSS_CHECK_RESERVE_S + 130):
            result['groups'].append(group(name, refs, [3, 2, 1, 0], 'rotAll', 512))
            save(name + '.summary.json', result)
        else:
            result['skipped'].append('rotation all-four: not enough window time')
        result['loss_check'] = group(name, refs, [3, 2, 1, 0], 'loss', LOSS_TOKENS)
        save(name + '.summary.json', result)
        snap(name, 'after-loss-check')
        save(name + '.final-metrics.json', api('/metrics', timeout=10))
        vram_floor(name, 'after-loss-check')
        result['all_groups_above_120000'] = all((g['all_above_120000'] for g in result['groups']))
        result['passed'] = result['all_groups_above_120000'] and result['loss_check']['all_above_120000']
        if not result['passed']:
            result['error'] = 'a continuation did not reuse its prefix (groups=%s, loss check=%s)' % ([g['cache_n'] for g in result['groups']], result['loss_check']['cache_n'])
    except BaseException as exc:
        result.update(passed=False, error=repr(exc))
        event('phase-fail', phase=name, error=repr(exc))
        if isinstance(exc, (BudgetError, FloorError)):
            fatal = exc
    finally:
        finished.set()
        timer.join(timeout=90)
        result['budget_censored'] = (E / (name + '.budget-censored.json')).exists()
        if result['budget_censored']:
            result['passed'] = False
        try:
            snap(name, 'end')
        except BaseException:
            pass
        try:
            finish_engine(name, logpath)
        except BaseException as exc:
            result.update(passed=False, finish_error=repr(exc))
        try:
            rc, g = call(['free', '-m'])
            result['free_m_after'] = g
        except BaseException:
            pass
        result['end'] = time.time()
        save(name + '.summary.json', result)
    return (result, fatal)

def run():
    global START
    assert digest() == DIGEST, 'production launcher changed'
    assert not (E / 'window.json').exists(), 'window already used'
    START = time.time()
    health(int(START))
    save('preflight.json', dict(time=START, launcher_sha256=digest(), engine_sha256=NATIVE_SHA, driver_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()))
    START = time.time()
    state = dict(start=START, hard_stop=START + HARDMIN * 60, test_deadline=START + MAXMIN * 60, driver=dict(pid=os.getpid(), start=ident(os.getpid())))
    save('window.json', state)
    with (E / 'guard.log').open('w') as f:
        g = subprocess.Popen([sys.executable, str(__file__), MODE, 'guard'], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    until = time.monotonic() + 10
    while not (E / 'guard-armed.json').exists():
        if g.poll() is not None or time.monotonic() > until:
            raise RuntimeError('restore guard did not arm')
        time.sleep(0.1)
    (E / 'production-down').write_text(str(START))
    event('production-stop-start')
    try:
        rc, out = call(['bash', HOME / 'production/stop.sh'], 90)
        (E / 'production-stop.log').write_text(out)
        if rc or 'SUCCESS' not in out:
            raise RuntimeError('production stop not confirmed')
        event('production-stopped')
        assert not engine_pids(), 'a model engine still runs after the production stop'
        for name, pc, deadline_min in [('X4', False, 24.0)]:
            if time.time() >= START + NO_NEW_CANDIDATE_MIN * 60:
                save(name + '.not-started.json', dict(reason='no new candidate after minute %d' % NO_NEW_CANDIDATE_MIN, time=time.time()))
                break
            if (E / 'guard-abort.json').exists():
                break
            row, fatal = phase(name, pc, deadline_min)
            health(int(START))
            if fatal is not None:
                save('window-stopped.json', dict(reason=repr(fatal), candidate=name))
                break
    except BaseException as exc:
        save('driver-failure.json', dict(error=repr(exc), time=time.time()))
        traceback.print_exc()
    finally:
        save('finish.json', dict(reason='window ' + MODE + ' tests ended', time=time.time()))
    until = START + (HARDMIN + 10) * 60
    while not (E / 'restore-validation.json').exists() and time.time() < until:
        if (E / 'restore-failed.json').exists():
            raise RuntimeError('guard restoration failed')
        time.sleep(1)
    assert json.loads((E / 'restore-validation.json').read_text())['ok'], 'production restoration not verified'
if __name__ == '__main__':
    E.mkdir(exist_ok=True)
    if sys.argv[2:3] == ['guard']:
        guard()
    else:
        run()
