# Sanitized archival driver; original lifecycle code is retained for inspection.
# Local installation paths/endpoints and synthetic inputs have been omitted.
# This file is deliberately disabled, including when imported.
raise RuntimeError('Archive only: adapt paths, fixtures, ownership and restoration before use.')
import concurrent.futures as cf
import hashlib, json, os, pathlib, signal, subprocess, sys, threading, time, traceback, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent
E = ROOT / 'evidence'
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
    engines = []
    expected = str(ROOT / 'build/src/split/strata-split-2')
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if os.readlink(proc / 'exe') == expected:
                pid = int(proc.name)
                if os.getpgid(pid) == pid:
                    engines.append(dict(pid=pid, start=ident(pid)))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    p = E / 'candidate.json'
    if p.exists():
        stop_group(json.loads(p.read_text()))
    for record in engines:
        stop_group(record)

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
                    reason = 'absolute 60 minute hard stop'
                elif now >= state['restore_at']:
                    reason = 'minute21 restore deadline'
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
        result = dict(label=label, send=start, end=time.monotonic(), first=events[0] if events else None, last=events[-1] if events else None, fragments=len(events), usage=usage, timings=timings, text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
        save(label + '.result.json', result)
        if usage.get('completion_tokens') != limit:
            raise RuntimeError('completion length ' + str(usage))
        return result
    except BaseException as exc:
        save(label + '.error.json', dict(error=repr(exc), usage=usage, timings=timings, fragments=len(events)))
        STOP.set()
        candidate_stop()
        raise

def pair(a, b, la, lb, tag, stagger=False):
    ready = threading.Event()
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(request, a, la, tag + '-A', ready)
        if stagger:
            until = time.monotonic() + 45
            while not ready.wait(0.05):
                if fa.done() or time.monotonic() > until:
                    raise RuntimeError('writer never started')
        fb = pool.submit(request, b, lb, tag + '-B')
        rows = [f.result() for f in cf.as_completed([fa, fb])]
    if stagger:
        aa = next((r for r in rows if r['label'].endswith('-A')))
        bb = next((r for r in rows if r['label'].endswith('-B')))
        if not aa['first'] <= bb['send'] < aa['last']:
            raise RuntimeError('no actual writer overlap')
        reuse = bb['timings'].get('cache_n', bb['usage'].get('prompt_tokens_details', {}).get('cached_tokens'))
        if reuse is None or reuse > 256:
            raise RuntimeError('read was not proven cold ' + str(reuse))
    elif tag.endswith('-S3'):
        if any((r['first'] is None for r in rows)) or max((r['first'] for r in rows)) >= min((r['last'] for r in rows)):
            raise RuntimeError('S3 lacked simultaneous emission')
    return rows

def short(lane):
    return [{'role': 'user', 'content': '<synthetic input omitted>'}]

def fixture(kind):
    if kind == '96k':
        source = fixture('128k')
        text = ' '.join(source.split()[:95880]) + '<synthetic input omitted>'
        save('fixture96k.json', dict(source='128k.json first 95880 whitespace words', sha256=hashlib.sha256(text.encode()).hexdigest(), text=text))
        return text
    return json.loads((HOME / f'benchmark/tp-truth-recipe-fixtures/{kind}.json').read_text())[0]['content']

def arm(name, ram=36, peer=0, pf=0, extra=None, kind='128k', first64=False):
    if time.time() >= START + 17 * 60:
        raise RuntimeError('no new arm after minute17')
    if (E / 'guard-abort.json').exists():
        raise RuntimeError('guard ended window')
    STOP.clear()
    cfg = json.loads(TEMPLATE.read_text())
    cfg.pop('split_fallback', None)
    cfg.update(exe=str(ROOT / 'build/src/split/strata-split-2'), cwd=str(ROOT / 'source'), log=str(E / (name + '.engine.log')), engine_ready_s=180)
    cfg['env'] = {'STRATA_ROUTE_TAIL_SKIP': '0', 'FNX_ARENA': '1', 'FNX_EXPERT_RAM_GIB': str(ram), 'FNX_ARENA_RESERVE_MIB': '640', 'FNX_PEER': str(peer), 'FNX_PF_PEER': str(pf), 'FNX_RING_F32': '0', **(extra or {})}
    save(name + '.config.json', cfg)
    event('arm-start', arm=name, ram=ram, peer=peer, pf=pf, extra=extra)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('FNX_', 'STRATA_'))}
    env.update(cfg['env'])
    env.update(XDG_STATE_HOME=str(ROOT / (name + '.state')), STRATA_PROFILE_DIR=str(ROOT / (name + '.profiles')), STRATA_RUNTIME_DIR=str(ROOT / (name + '.runtime')), LD_LIBRARY_PATH='<local path>' + env.get('LD_LIBRARY_PATH', ''))
    log = (E / (name + '.server.log')).open('w')
    p = subprocess.Popen([str(PY), '-m', 'serve.server', '--engine', 'strata', '--config', str(E / (name + '.config.json')), '--host', '<local endpoint>', '--port', '18082', '--parallel', '2'], cwd=ROOT / 'source', env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    save('candidate.json', dict(pid=p.pid, start=ident(p.pid), arm=name))
    result = dict(arm=name, start=time.time(), ram=ram, peer=peer, pf=pf, extra=extra, stages=[])
    try:
        until = time.monotonic() + 180
        while True:
            if p.poll() is not None:
                raise RuntimeError('server exited ' + str(p.returncode))
            try:
                api(timeout=2)
                break
            except Exception:
                if time.monotonic() > until:
                    raise TimeoutError('server ready timeout')
                time.sleep(1)
        health(int(START))
        actual = []
        for proc in pathlib.Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if os.readlink(proc / 'exe') == cfg['exe']:
                    actual.append(dict(pid=int(proc.name), args=(proc / 'cmdline').read_bytes().decode().split('\x00'), sha256=hashlib.sha256(pathlib.Path(cfg['exe']).read_bytes()).hexdigest()))
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                pass
        save(name + '.actual-process.json', actual)
        if len(actual) != 1:
            raise RuntimeError('expected exactly one task split engine')
        rc, g = call(['nvidia-smi', '--query-gpu=index,memory.free', '--format=csv,noheader,nounits'])
        save(name + '.loaded-vram.json', dict(rc=rc, gpus=g))
        if rc or any((int(r.split(',')[1]) < 300 for r in g.strip().splitlines())):
            raise RuntimeError('startup VRAM floor')
        pair(short('S1A'), short('S1B'), 64, 64, name + '-S1')
        result['stages'].append('S1 pass')
        event('stage-pass', arm=name, stage='S1')
        for k in ['64k', kind] if first64 else [kind]:
            b = [{'role': 'user', 'content': '<synthetic input omitted>'}]
            pair(short('S2'), b, 2048, 512, name + '-S2-' + k, True)
            result['stages'].append('S2 ' + k + ' pass')
            event('stage-pass', arm=name, stage='S2 ' + k)
        base = b[0]['content']
        messages = [[{'role': 'user', 'content': '<synthetic input omitted>'}] for i in range(2)]
        rows = pair(*messages, 64, 64, name + '-S3')
        result['S3_reuse'] = [dict(prompt_tokens=r['usage'].get('prompt_tokens'), cache_n=r['timings'].get('cache_n'), prompt_n=r['timings'].get('prompt_n')) for r in rows]
        if kind == '128k' and any(((r['usage'].get('prompt_tokens') or 0) < 128000 or (r['timings'].get('cache_n') or 0) < 120000 for r in rows)):
            raise RuntimeError('S3 long shared-prefix reuse unconfirmed')
        result['stages'].append('S3 pass')
        result['passed'] = True
    except BaseException as exc:
        result.update(passed=False, error=repr(exc))
        event('arm-fail', arm=name, error=repr(exc))
    finally:
        candidate_stop()
        p.wait(timeout=20)
        log.close()
        result['end'] = time.time()
        save(name + '.summary.json', result)
    engine = (E / (name + '.engine.log')).read_text(errors='replace')
    result['placement_lines'] = [line for line in engine.splitlines() if any((s in line for s in ['arena:', 'in RAM', 'expert cache', 'peer push', 'Peer push', 'slot(s);']))]
    if ram == 44:
        result['no_lending_confirmed'] = not any(('arena: K/V pool' in line for line in engine.splitlines()))
        if not result['no_lending_confirmed']:
            save(name + '.summary.json', result)
            raise RuntimeError('RAM44 still grew lent pool; branch premise unconfirmed')
    save(name + '.summary.json', result)
    event('arm-end', **result)
    if (E / 'hardware-abort.log').exists() or (E / 'guard-abort.json').exists():
        raise RuntimeError('hardware/guard abort; no more arms')
    health(int(START))
    return result['passed']

def run():
    global START
    assert digest() == DIGEST, 'production launcher changed'
    health(int(time.time()))
    START = time.time()
    state = dict(start=START, restore_at=START + 1260, hard_stop=START + 3600, driver=dict(pid=os.getpid(), start=ident(os.getpid())))
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
        rc, out = call([ROOT / 'build/src/split/split_router_guard_test'], 60)
        (E / 'router-guard-test.log').write_text(out)
        save('router-guard-test.json', dict(rc=rc, time=time.time()))
        if rc:
            raise RuntimeError('router regression failed')
        health(int(START))
        event('router-guard-pass')
        a = arm('arm1-host-r36')
        if not a:
            b = arm('arm2-host-r44', ram=44)
            if b:
                c = arm('arm3-churn32', extra={'FNX_ARENA_BASE_PAGES': '100', 'FNX_ARENA_CHURN': '1'}, kind='32k')
                if c:
                    arm('arm4-churn96', extra={'FNX_ARENA_BASE_PAGES': '100', 'FNX_ARENA_CHURN': '1'}, kind='96k')
            else:
                arm('arm3-no-capture-r44', ram=44, extra={'FNX_CAPTURE_AFTER': '1000000'})
        else:
            b = arm('arm2-peer-r36', peer=1, pf=1)
            if b:
                arm('arm3-peer64-first', peer=1, pf=1, first64=True)
            else:
                arm('arm3-peer-parts1', peer=1, pf=0, extra={'FNX_PEER_PARTS': '1'})
                arm('arm4-peer-parts2', peer=1, pf=0, extra={'FNX_PEER_PARTS': '2'})
        save('finish.json', dict(reason='approved diagnostic arms complete', time=time.time()))
    except BaseException as exc:
        save('driver-failure.json', dict(error=repr(exc), time=time.time()))
        traceback.print_exc()
        save('finish.json', dict(reason='driver finished: ' + repr(exc), time=time.time()))
    until = START + 1500
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
