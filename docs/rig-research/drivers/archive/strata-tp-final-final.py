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
MAXMIN = 25 if MODE == 'A' else 30
ENGINE_SHA = (ROOT / 'engine.sha256').read_text().split()[0]
HOME = pathlib.Path.home()
PY = HOME / 'benchmark/src/vllm-2080ti-definitive-0.2.x/.venv/bin/python'
DIGEST = '3701dbc6ffcfee6cf09cd918e8bf1c7145fc492216bcf9f3d16d08973ff4357b'
TEMPLATE = HOME / 'benchmark/tp-truth-programme-20261115/windows/wave5b/TP-R36-RSV640-B2-fit.state/strata/launch/ud-iq4_xs-128k.json'

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

def digest():
    return hashlib.sha256((HOME / 'production/start.sh').read_bytes()).hexdigest()

def ident(pid):
    try:
        return pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()[19]
    except FileNotFoundError:
        return None

def owned(record):
    return ident(record['pid']) == record['start']

def stop_group(record):
    if not owned(record):
        return
    try:
        os.killpg(record['pid'], signal.SIGTERM)
    except ProcessLookupError:
        return
    until = time.monotonic() + 12
    while owned(record) and time.monotonic() < until:
        time.sleep(0.1)
    try:
        os.killpg(record['pid'], signal.SIGKILL)
    except ProcessLookupError:
        pass

def candidate_stop():
    ns = E / 'native-namespace.json'
    if ns.exists():
        env = os.environ.copy()
        env.update(json.loads(ns.read_text()))
        rc, out = call_env([HOME / 'benchmark/bin/strata', 'launch', '--stop'], env, 60)
        (E / 'native-stop.log').write_text(out)
    records = []
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            exe = os.readlink(proc / 'exe')
            if exe == str(ROOT / 'build/src/split/strata-split-2'):
                pid = int(proc.name)
                if os.getpgid(pid) == pid:
                    records.append(dict(pid=pid, start=ident(pid)))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    f = E / 'candidate.json'
    if f.exists():
        stop_group(json.loads(f.read_text()))
    for r in records:
        stop_group(r)

def call_env(args, env, timeout):
    p = subprocess.run([str(x) for x in args], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return (p.returncode, p.stdout)

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

def request(messages, limit, label, on_first=None):
    payload = dict(model='qwen3.8', messages=messages, temperature=0, max_tokens=limit, seed=40261114, stream=True, stream_options={'include_usage': True}, stop=['<|im_end|>', '<|endoftext|>'], reasoning_effort='none', chat_template_kwargs={'enable_thinking': False})
    save(label + '.input.json', payload)
    req = urllib.request.Request('http://<local endpoint>:18082/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    assert time.time() < START + 1200, 'no request after minute20'
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
                    raise RuntimeError('arm already failed')
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
        save(label + '.error.json', dict(error=repr(exc), usage=usage, timings=timings, fragments=len(events)))
        STOP.set()
        raise
NATIVE_SHA = '4f7ad93a13360398b0f97c7161c4b779c7125217e63f77a0abc0fde04add9c66'

def start_tp(name, spec, extra=None):
    cfg = json.loads(TEMPLATE.read_text())
    cfg.pop('split_fallback', None)
    cfg.update(exe=str(ROOT / 'build/src/split/strata-split-2'), cwd=str(ROOT / 'source'), log=str(E / (name + '.engine.log')), engine_ready_s=180)
    cfg['env'] = {'STRATA_ROUTE_TAIL_SKIP': '0', 'FNX_ARENA': '1', 'FNX_EXPERT_RAM_GIB': '36', 'FNX_ARENA_RESERVE_MIB': '640', 'FNX_PEER': '1', 'FNX_PF_PEER': '1', 'FNX_RING_F32': '0'}
    cfg['env'].update(extra or {})
    for key in ['args', 'args_written', 'args_derived']:
        if key in cfg:
            cfg[key][cfg[key].index('--spec') + 1] = str(spec)
    save(name + '.config.json', cfg)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('FNX_', 'STRATA_'))}
    env.update(cfg['env'])
    env.update(XDG_STATE_HOME=str(ROOT / (name + '.state')), STRATA_PROFILE_DIR=str(ROOT / (name + '.profiles')), STRATA_RUNTIME_DIR=str(ROOT / (name + '.runtime')), LD_LIBRARY_PATH='<local path>' + env.get('LD_LIBRARY_PATH', ''))
    log = (E / (name + '.server.log')).open('w')
    p = subprocess.Popen([str(PY), '-m', 'serve.server', '--engine', 'strata', '--config', str(E / (name + '.config.json')), '--host', '<local endpoint>', '--port', '18082', '--parallel', '2'], cwd=ROOT / 'source', env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    save('candidate.json', dict(pid=p.pid, start=ident(p.pid), arm=name))
    until = time.monotonic() + 180
    while True:
        if p.poll() is not None:
            raise RuntimeError('TP server exited ' + str(p.returncode))
        try:
            api(timeout=2)
            break
        except Exception:
            if time.monotonic() > until:
                raise TimeoutError('TP readiness timeout')
            time.sleep(1)
    return E / (name + '.engine.log')

def start_native(name):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('FNX_', 'STRATA_'))}
    namespace = {'XDG_STATE_HOME': str(ROOT / (name + '.state')), 'STRATA_PROFILE_DIR': str(ROOT / (name + '.profiles')), 'STRATA_RUNTIME_DIR': str(ROOT / (name + '.runtime'))}
    env.update(namespace)
    save('native-namespace.json', namespace)
    args = [HOME / 'benchmark/bin/strata', 'launch', '--model-path', HOME / '<model path>', '--model', 'ud-iq4_xs', '--family', 'unsloth', '--data-dir', HOME / '<model path>', '--context', '256k', '--kv', 'int8', '--vision', 'on', '--parallel', '2', '--drafting', 'mtp', '--access', 'local', '--port', '18082', '--tune', 'skip', '--yes', '--no-tui', '--split-engine', 'off']
    settings = ['STRATA_BF16_TC=1', 'STRATA_GDN_CONVL2=2', 'spec=3', 'pipeline_windows=1', 'STRATA_PF_GROUP_SCRATCH=1', 'STRATA_PF_HC_REGION=1', 'layer-split=23', 'trim-stage-weights=1', 'STRATA_STAGE_TRIM=1', 'batch-mtp=1', 'STRATA_PIPED_MTP=1', 'STRATA_BATCH_SELF_COMMIT=0', 'STRATA_PIPED_CONCURRENT=0', 'STRATA_SM75_PERF=0', 'prefill-pipe=0']
    for s in settings:
        args += ['--set', s]
    save(name + '.launch.json', dict(args=list(map(str, args)), namespace=namespace))
    rc, out = call_env(args, env, 240)
    (E / (name + '.launch.log')).write_text(out)
    if rc:
        raise RuntimeError('R2 launch failed ' + out[-1000:])
    api()
    return pathlib.Path(namespace['XDG_STATE_HOME']) / 'strata/launch/ud-iq4_xs-256k.engine.log'

def identity(name, native, spec):
    actual = []
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = proc.joinpath('cmdline').read_bytes().decode().strip('\x00').split('\x00')
            if '--native' not in args:
                continue
            exe = os.readlink(proc / 'exe')
            if not pathlib.Path(exe).name.startswith('strata'):
                continue
            env = dict((s.split('=', 1) for s in proc.joinpath('environ').read_bytes().decode().strip('\x00').split('\x00') if '=' in s))
            actual.append(dict(pid=int(proc.name), args=args, exe=exe, sha256=hashlib.sha256(pathlib.Path(exe).read_bytes()).hexdigest(), env={k: v for k, v in env.items() if k.startswith(('FNX_', 'STRATA_')) and (not re.search('KEY|TOKEN|SECRET|PASSWORD', k))}))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    save(name + '.actual-process.json', actual)
    assert len(actual) == 1, 'expected one model engine; no overlap'
    r = actual[0]
    args = r['args']
    env = r['env']
    assert r['sha256'] == (NATIVE_SHA if native else ENGINE_SHA)

    def arg(k):
        return args[args.index(k) + 1]
    assert arg('--batch') == '2'
    if native:
        assert arg('--max-context') == '262144' and arg('--spec') == '3'
        assert arg('--layer-split') == '23' and arg('--kv') == 'int8'
        assert ('--conversation-cache-mib' not in args or arg('--conversation-cache-mib') == '8192') and '--vision' in args
        assert arg('--kv-resident') == '32768'
        assert '--trim-stage-weights' in args and '--batch-mtp' in args
        assert env.get('STRATA_STAGE_TRIM') == '1' and env.get('STRATA_PIPED_MTP') == '1' and (env.get('STRATA_BATCH_SELF_COMMIT') == '0')
        assert env.get('STRATA_PIPED_CONCURRENT', '0') == '0' and env.get('STRATA_SM75_PERF', '0') == '0'
        assert '--prefill-pipe' not in args or arg('--prefill-pipe') == '0'
    else:
        assert arg('--max-context') == '131072' and arg('--spec') == str(spec) and (arg('--lookup') == '15')
        for k, v in {'FNX_PEER': '1', 'FNX_PF_PEER': '1', 'FNX_RING_F32': '0', 'FNX_EXPERT_RAM_GIB': '36', 'FNX_ARENA_RESERVE_MIB': '640'}.items():
            assert env[k] == v
    rc, g = call(['nvidia-smi', '--query-gpu=index,memory.free', '--format=csv,noheader,nounits'])
    save(name + '.loaded-vram.json', dict(rc=rc, gpus=g))
    assert rc == 0 and all((int(row.split(',')[1]) >= 300 for row in g.strip().splitlines())), 'VRAM floor'

def metrics():
    return api('/metrics')

def summary_row(row):
    n = row['usage']['completion_tokens']
    span = row['last'] - row['first']
    return dict(label=row['label'], n=n, decode_tok_s=(n - 1) / span, engine_decode_tok_s=row['timings'].get('predicted_per_second'), ttft_s=row['first'] - row['send'], cache_n=row['timings'].get('cache_n'), max_gap_s=max((b - a for a, b in zip(row['events'], row['events'][1:]))), marker_present='TP-TRUTH-WAREHOUSE' in row['text'])

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
        rows.append(row)
        save('host-probe-' + phase + '.json', rows)
        if rc or not match:
            raise RuntimeError('host probe failed ' + out[-500:])
        event('host-probe', **row)
    return rows
LONG = '<synthetic input omitted>'

def suffix(tag):
    raise RuntimeError('Synthetic fixtures are omitted; provide newly generated inputs.')

def deadline():
    if time.time() >= START + (MAXMIN - 5) * 60:
        raise RuntimeError('no new arm after max minus five minutes')
    if (E / 'guard-abort.json').exists():
        raise RuntimeError('guard ended window')

def start_checked(name, native=False, flags=None):
    deadline()
    STOP.clear()
    probe(name + '-before')
    logpath = start_native(name) if native else start_tp(name, 6, flags)
    save('active-log.json', str(logpath))
    identity(name, native, 6)
    health(int(START))
    return logpath

def finish_engine(name, logpath):
    probe(name + '-after')
    candidate_stop()
    if logpath and logpath.exists() and (logpath != E / (name + '.engine.log')):
        (E / (name + '.engine.log')).write_bytes(logpath.read_bytes())
    health(int(START))

def arm_a(name, flags):
    result = dict(name=name, flags=flags, start=time.time())
    logpath = None
    try:
        logpath = start_checked(name, flags=flags)
        fixture = HOME / 'benchmark/tp-truth-recipe-fixtures/128k.json'
        ref = json.loads(fixture.read_text())
        save(name + '.fixture.json', dict(path=str(fixture), sha256=hashlib.sha256(fixture.read_bytes()).hexdigest()))
        cold = request(ref[:1], 512, name + '-cold')
        nonce = hashlib.sha256(b'128k:9200:0:tp-truth-v1').hexdigest()[:12]
        tag = f'Synthetic benchmark seed {20261114 + 9200 * 101}, nonce {nonce}. '
        warm = request(ref + [suffix(tag).copy() | {'content': '<synthetic input omitted>'}], 512, name + '-warm')
        result.update(cold=summary_row(cold), warm=summary_row(warm), hashes=[cold['sha256'], warm['sha256']])
        expected = json.loads((ROOT / 'window3-hashes.json').read_text()) if name == 'A0' else json.loads((E / 'A0.summary.json').read_text())['hashes']
        result['hash_equal'] = result['hashes'] == expected
        if not result['hash_equal']:
            raise RuntimeError('greedy output differs from ' + ('window3' if name == 'A0' else 'A0'))
        assert warm['timings'].get('cache_n', 0) > 0, 'warm cache missing'
        result['passed'] = True
    except BaseException as exc:
        result.update(passed=False, error=repr(exc))
        event('arm-fail', arm=name, error=repr(exc))
    finally:
        try:
            finish_engine(name, logpath)
        except BaseException as exc:
            result.update(passed=False, finish_error=repr(exc))
        result['end'] = time.time()
        save(name + '.summary.json', result)
    event('arm-complete', **result)
    return result

def fixtures():
    raise RuntimeError('Synthetic fixtures are omitted; provide newly generated inputs.')

def pair(name, refs, round_, limit=512, firsts=None):
    bar = threading.Barrier(2)

    def work(lane):
        messages = refs[lane] + [suffix(f'Synthetic final nonce {name}-{round_}-{lane}.')]
        bar.wait(timeout=10)
        return request(messages, limit, f'{name}-r{round_}-lane{lane}', None if firsts is None else firsts[lane])
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        fut = [pool.submit(work, i) for i in range(2)]
        done, _ = cf.wait(fut, return_when=cf.FIRST_EXCEPTION)
        if any((f.exception() for f in done)):
            STOP.set()
            candidate_stop()
        rows = [f.result() for f in fut]
    out = dict(round=round_, rows=[summary_row(r) for r in rows], wall_aggregate_tok_s=2 * limit / (max((r['end'] for r in rows)) - min((r['send'] for r in rows))), send_skew_s=abs(rows[0]['send'] - rows[1]['send']), emission_overlap_s=min((r['last'] for r in rows)) - max((r['first'] for r in rows)))
    save(f'{name}-r{round_}.pair.json', out)
    event('pair-complete', phase=name, **out)
    out['both_reused'] = all(((r['timings'].get('cache_n') or 0) > 0 for r in rows))
    save(f'{name}-r{round_}.pair.json', out)
    return out

def fairness(name, refs):
    firsts = [threading.Event(), threading.Event()]
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        decoding = pool.submit(pair, name, refs, 'fair', 2048, firsts)
        assert all((x.wait(timeout=240) for x in firsts)), 'decoding lanes failed to start'
        arrived = time.monotonic()
        cold = request(refs[2][:1], 512, name + '-fair-third')
        p = decoding.result()
    overlap = []
    for lane in range(2):
        r = json.loads((E / f'{name}-rfair-lane{lane}.result.json').read_text())
        times = [t for t in r['events'] if arrived <= t <= cold['first']]
        overlap.append(dict(lane=lane, fragments_during_third_wait=len(times), decoding_at_third_arrival=r['first'] <= arrived < r['last'], fragment_rate_per_s=len(times) / max(0.001, min(r['last'], cold['first']) - arrived), decode_ended_before_third_first=r['last'] <= cold['first']))
    out = dict(third=summary_row(cold), third_send=arrived, lanes=overlap, pair=p, both_decoding_at_arrival=all((x['decoding_at_third_arrival'] for x in overlap)))
    save(name + '.fairness.json', out)
    event('fairness-complete', phase=name, **out)
    return out

def phase_b(name, native, flags):
    result = dict(name=name, native=native, flags=flags, start=time.time(), rounds=[])
    logpath = None
    try:
        logpath = start_checked(name, native, flags)
        refs = fixtures()
        for lane in range(2):
            cold = request(refs[lane][:1], 512, f'{name}-prime{lane}')
            result[f'prime{lane}'] = summary_row(cold)
        for i in range(1, 4):
            result['rounds'].append(pair(name, refs, i))
            save(name + '.summary.json', result)
        result['fairness'] = fairness(name, refs)
        end = time.monotonic() + 240
        i = 0
        while time.monotonic() < end and time.time() < START + MAXMIN * 60 - 30:
            i += 1
            result['rounds'].append(pair(name, refs, 'sustain' + str(i)))
            save(name + '.summary.json', result)
        result['sustain_pairs'] = i
        result['passed'] = all((x['both_reused'] for x in result['rounds']))
        if not result['passed']:
            result['error'] = 'one or more paired continuations did not reuse both prefixes'
    except BaseException as exc:
        result.update(passed=False, error=repr(exc))
        event('phase-fail', phase=name, error=repr(exc))
    finally:
        try:
            finish_engine(name, logpath)
        except BaseException as exc:
            result.update(passed=False, finish_error=repr(exc))
        result['end'] = time.time()
        save(name + '.summary.json', result)
    return result

def run():
    global START
    assert digest() == DIGEST, 'production launcher changed'
    assert hashlib.sha256((ROOT / 'build/src/split/strata-split-2').read_bytes()).hexdigest() == ENGINE_SHA
    assert not (E / 'window.json').exists(), 'window already used'
    START = time.time()
    health(int(START))
    save('preflight.json', dict(time=START, launcher_sha256=digest(), engine_sha256=ENGINE_SHA))
    if MODE == 'A':
        samples = probe('fast-gate')
        if min((x['memcpy_GB_s'] for x in samples)) < 9:
            save('fast-gate-failed.json', samples)
            return
    if MODE == 'B':
        assert json.loads((ROOT / 'evidence-A/restore-validation.json').read_text())['ok'], 'A not restored'
    START = time.time()
    state = dict(start=START, hard_stop=START + (MAXMIN + 5) * 60, test_deadline=START + MAXMIN * 60, driver=dict(pid=os.getpid(), start=ident(os.getpid())))
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
        if MODE == 'A':
            rc, out = call([ROOT / 'build/src/split/split_router_guard_test'], 90)
            (E / 'router-guard.log').write_text(out)
            save('router-guard.json', dict(rc=rc))
            if rc:
                raise RuntimeError('split_router_guard_test failed')
            arms = [('A0', {}), ('A1', {'FNX_CACHE_COPY_STATS': '1'}), ('A2', {'FNX_CACHE_COPY_ENGINE': '1', 'FNX_CACHE_COPY_STATS': '1'}), ('A3', {'FNX_CACHE_COPY_ENGINE': '1', 'FNX_CACHE_COPY_STATS': '1', 'FNX_CACHE_PREFETCH': '1'})]
            for name, flags in arms:
                row = arm_a(name, flags)
                if not row.get('passed') and name == 'A0':
                    break
                health(int(START))
                deadline()
        else:
            best = json.loads((ROOT / 'best-flags.json').read_text())
            for name, native, flags in [('B0', False, best), ('B1', False, {**best, 'FNX_READ_INTERLEAVE': '1'}), ('R2', True, {})]:
                phase_b(name, native, flags)
                health(int(START))
                deadline()
    except BaseException as exc:
        save('driver-failure.json', dict(error=repr(exc), time=time.time()))
        traceback.print_exc()
    finally:
        save('finish.json', dict(reason='window ' + MODE + ' tests ended', time=time.time()))
    until = START + (MAXMIN + 10) * 60
    while not (E / 'restore-validation.json').exists() and time.time() < until:
        if (E / 'restore-failed.json').exists():
            raise RuntimeError('guard restoration failed')
        time.sleep(1)
    assert json.loads((E / 'restore-validation.json').read_text())['ok'], 'production restoration not verified'
if __name__ == '__main__':
    E.mkdir(exist_ok=True)
    if sys.argv[2] == 'guard':
        guard()
    else:
        run()
