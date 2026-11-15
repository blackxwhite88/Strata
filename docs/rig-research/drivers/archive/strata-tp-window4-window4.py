# Sanitized archival driver; original lifecycle code is retained for inspection.
# Local installation paths/endpoints and synthetic inputs have been omitted.
# This file is deliberately disabled, including when imported.
raise RuntimeError('Archive only: adapt paths, fixtures, ownership and restoration before use.')
import re
import concurrent.futures as cf
import hashlib, json, os, pathlib, signal, subprocess, sys, threading, time, traceback, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent
E = ROOT / 'evidence-window4'
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
                    reason = 'minute26 restore deadline (hard stop)'
                elif now >= state['test_deadline']:
                    reason = 'minute20 test budget; restore now'
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
    start = time.monotonic()
    events = []
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
                        if on_first is not None:
                            on_first.set()
        result = dict(label=label, send=start, end=time.monotonic(), first=events[0] if events else None, last=events[-1] if events else None, fragments=len(events), events=events, usage=usage, timings=timings, text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
        save(label + '.result.json', result)
        if usage.get('completion_tokens') != limit:
            raise RuntimeError('completion length ' + str(usage))
        return result
    except BaseException as exc:
        save(label + '.error.json', dict(error=repr(exc), usage=usage, timings=timings, fragments=len(events)))
        STOP.set()
        raise
NATIVE_SHA = '4f7ad93a13360398b0f97c7161c4b779c7125217e63f77a0abc0fde04add9c66'

def start_tp(name, spec):
    cfg = json.loads(TEMPLATE.read_text())
    cfg.pop('split_fallback', None)
    cfg.update(exe=str(ROOT / 'build/src/split/strata-split-2'), cwd=str(ROOT / 'source'), log=str(E / (name + '.engine.log')), engine_ready_s=180)
    cfg['env'] = {'STRATA_ROUTE_TAIL_SKIP': '0', 'FNX_ARENA': '1', 'FNX_EXPERT_RAM_GIB': '36', 'FNX_ARENA_RESERVE_MIB': '640', 'FNX_PEER': '1', 'FNX_PF_PEER': '1', 'FNX_RING_F32': '0'}
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
    assert r['sha256'] == (NATIVE_SHA if native else '2e7ee4deb0a1bc65f3ad9e9bb212cd37283243c1163a42acac867f8852051da1')

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

def phase(name, native=False, spec=6):
    assert time.time() < START + 1200, 'no phase after minute20'
    assert not (E / 'guard-abort.json').exists(), 'guard ended window'
    STOP.clear()
    result = dict(phase=name, start=time.time(), native=native, spec=spec, rounds=[])
    logpath = None
    probed = False
    event('phase-start', phase=name)
    try:
        logpath = start_native(name) if native else start_tp(name, spec)
        identity(name, native, spec)
        health(int(START))
        probe(name + '-before')
        probed = True
        reference = json.loads((HOME / 'benchmark/tp-truth-recipe-fixtures/128k.json').read_text())
        cold = request(reference[:1], 512, name + '-cold')
        result['cold'] = summary_row(cold)
        if native:
            txt = logpath.read_text(errors='replace')
            assert re.search('STRATA_PIPED_MTP: \\d+ pipelined groups?', txt), 'piped MTP not active'
            assert 'WARNING: STRATA_PIPED_MTP is off' not in txt
            assert '32768' in txt, 'resident KV startup identity missing'
        for round_ in range(1, 4):
            assert time.time() < START + 1200, 'no round after minute20'
            bar = threading.Barrier(2)
            before = metrics()
            offset = logpath.stat().st_size

            def work(lane):
                nonce = hashlib.sha256(f'window4:128k:{round_}:{lane}'.encode()).hexdigest()[:12]
                tag = f'Synthetic benchmark seed 40261114, nonce {nonce}. '
                long = '<synthetic input omitted>'
                messages = reference + [{'role': 'user', 'content': '<synthetic input omitted>'}]
                bar.wait(timeout=10)
                return request(messages, 512, f'{name}-r{round_}-lane{lane}')
            with cf.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(work, lane) for lane in range(2)]
                done, pending = cf.wait(futures, return_when=cf.FIRST_EXCEPTION)
                if any((f.exception() for f in done)):
                    STOP.set()
                    candidate_stop()
                rows = [f.result() for f in futures]
            after = metrics()
            audit = after['totals']['requests'] - before['totals']['requests']
            for _ in range(10):
                if audit >= 2:
                    break
                time.sleep(0.1)
                after = metrics()
                audit = after['totals']['requests'] - before['totals']['requests']
            out = dict(round=round_, rows=[summary_row(r) for r in rows], wall_aggregate_tok_s=1024 / (max((r['end'] for r in rows)) - min((r['send'] for r in rows))), send_skew_s=abs(rows[0]['send'] - rows[1]['send']), emission_overlap_s=min((r['last'] for r in rows)) - max((r['first'] for r in rows)), audit_requests=audit, metrics_before=before, metrics_after=after)
            result['rounds'].append(out)
            save(name + '.summary.json', result)
            with logpath.open('rb') as f:
                f.seek(offset)
                (E / f'{name}-r{round_}.engine.txt').write_bytes(f.read())
            event('pair-complete', phase=name, round=round_, rows=out['rows'], wall_aggregate_tok_s=out['wall_aggregate_tok_s'], overlap_s=out['emission_overlap_s'])
            assert audit == 2, 'request audit mismatch'
            assert all((r['marker_present'] and (r['cache_n'] or 0) >= 127000 for r in out['rows'])), 'warm prefix or marker failed'
            health(int(START))
        result['passed'] = True
    except BaseException as exc:
        result.update(passed=False, error=repr(exc))
        event('phase-fail', phase=name, error=repr(exc))
    finally:
        if probed:
            try:
                probe(name + '-after')
            except BaseException as exc:
                result.update(passed=False, probe_error=repr(exc))
        candidate_stop()
        if logpath is not None and logpath.exists() and (logpath != E / (name + '.engine.log')):
            (E / (name + '.engine.log')).write_bytes(logpath.read_bytes())
        result['end'] = time.time()
        save(name + '.summary.json', result)
    health(int(START))
    return result.get('passed', False)

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

def run():
    global START
    assert digest() == DIGEST, 'production launcher changed'
    assert hashlib.sha256((ROOT / 'build/src/split/strata-split-2').read_bytes()).hexdigest() == '2e7ee4deb0a1bc65f3ad9e9bb212cd37283243c1163a42acac867f8852051da1', 'engine changed'
    assert not (E / 'window.json').exists(), 'window already used'
    save('preflight.json', dict(time=time.time(), launcher_sha256=digest(), engine_sha256=hashlib.sha256((ROOT / 'build/src/split/strata-split-2').read_bytes()).hexdigest(), old_drivers={n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in ['window.py', 'window2.py', 'test_window.py', 'window3.py']}))
    health(int(time.time()))
    fixture = HOME / 'benchmark/tp-truth-recipe-fixtures/128k.json'
    save('fixture-provenance.json', dict(path=str(fixture), sha256=hashlib.sha256(fixture.read_bytes()).hexdigest()))
    assert hashlib.sha256((HOME / 'benchmark/components-latest/engine/<local endpoint>-linux-x86_64-cuda/strata').read_bytes()).hexdigest() == NATIVE_SHA
    START = time.time()
    state = dict(start=START, restore_at=START + 1560, hard_stop=START + 1560, test_deadline=START + 1200, driver=dict(pid=os.getpid(), start=ident(os.getpid())))
    save('window.json', state)
    save('production-before.json', dict(time=START, digest=digest()))
    with (E / 'guard.log').open('w') as f:
        g = subprocess.Popen([sys.executable, str(__file__), 'guard'], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    until = time.monotonic() + 10
    while not (E / 'guard-armed.json').exists():
        if g.poll() is not None or time.monotonic() > until:
            raise RuntimeError('restore lease failed to arm')
        time.sleep(0.1)
    (E / 'production-down').write_text(str(START))
    event('production-stop-start')
    try:
        rc, out = call(['bash', HOME / 'production/stop.sh'], 90)
        (E / 'production-stop.log').write_text(out)
        if rc or 'SUCCESS' not in out:
            raise RuntimeError('production stop not confirmed')
        event('production-stopped')
        if not phase('W4-TP-spec6'):
            raise RuntimeError('TP phase failed; stop at first error')
        if not phase('W4-R2', native=True, spec=3):
            raise RuntimeError('R2 phase failed; stop at first error')
        if time.time() < START + 1020:
            if not phase('W4-TP-spec4', spec=4):
                raise RuntimeError('optional TP spec4 failed')
        else:
            save('optional-skipped.json', dict(reason='minute17 passed', time=time.time()))
        save('finish.json', dict(reason='paired warm continuation window complete', time=time.time()))
    except BaseException as exc:
        save('driver-failure.json', dict(error=repr(exc), time=time.time()))
        traceback.print_exc()
        save('finish.json', dict(reason='driver finished: ' + repr(exc), time=time.time()))
    until = START + 1550
    while not (E / 'restore-validation.json').exists() and time.time() < until:
        if (E / 'restore-failed.json').exists():
            raise RuntimeError('restoration failed; see evidence')
        time.sleep(1)
    if not (E / 'restore-validation.json').exists():
        raise TimeoutError('restoration verification missing')
    assert json.loads((E / 'restore-validation.json').read_text())['ok']
if __name__ == '__main__':
    E.mkdir(exist_ok=True)
    if sys.argv[1] == 'guard':
        guard()
    elif sys.argv[1] == 'run':
        run()
