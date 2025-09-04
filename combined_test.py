import argparse
import asyncio
import json
import random
import socket
import ssl
import statistics
import string
import time
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import requests

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore

############################################################
# URL Normalization
############################################################

def normalize_base_url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('http:') and not raw.startswith('http://'):
        raw = raw.replace('http:', '', 1)
    if raw.startswith('https:') and not raw.startswith('https://'):
        raw = raw.replace('https:', '', 1)
    raw = raw.lstrip('/')
    if not re.match(r'^https?://', raw):
        raw = 'http://' + raw
    parsed = urlparse(raw)
    host = parsed.hostname or 'localhost'
    port = parsed.port
    scheme = parsed.scheme
    netloc = host if port is None else f"{host}:{port}"
    return f"{scheme}://{netloc}".rstrip('/')

############################################################
# Functional Endpoint Tester (from test.py simplified)
############################################################

class FunctionalTester:
    """Comprehensive positive/negative functional tests mirroring standalone test.py."""
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.test_results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
        self.last_shaft_pid: str | None = None
        self.last_housing_pid: str | None = None

    def _log(self, endpoint: str, test_case: str, ok: bool, details: str = ""):
        status = 'PASS' if ok else 'FAIL'
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        entry = {
            'endpoint': endpoint,
            'test_case': test_case,
            'status': status,
            'details': details,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self.test_results.append(entry)
        print(f"{status} - {endpoint} - {test_case}{' - ' + details if (details and not ok) else ''}")

    def _req(self, method: str, endpoint: str, *, data: Dict | None = None, params: Dict | None = None, expected: int = 200):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == 'GET':
                r = requests.get(url, params=params, timeout=10)
            elif method == 'POST':
                r = requests.post(url, json=data, timeout=10)
            elif method == 'PUT':
                r = requests.put(url, json=data, timeout=10)
            elif method == 'DELETE':
                r = requests.delete(url, timeout=10)
            elif method == 'HEAD':
                r = requests.head(url, params=params, timeout=10)
            else:
                raise ValueError(method)
            payload = r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
            return {'code': r.status_code, 'body': payload, 'ok': r.status_code == expected}
        except Exception as e:
            return {'code': None, 'body': str(e), 'ok': False}

    # ---- individual tests ----
    def test_root(self):
        r = self._req('GET', '/')
        self._log('/', 'root reachable', r['ok'], f"code={r['code']}")

    def test_housing_types(self):
        r = self._req('GET', '/housing_types')
        ok = r['ok'] and isinstance(r['body'], dict) and {'oval','sqaure','angular'}.issubset(set(r['body'].get('housing_types', [])))
        self._log('/housing_types', 'list types', ok, f"code={r['code']}")

    def test_video_lists(self):
        categories = ['housing','shaft','oval_housing','sqaure_housing','angular_housing']
        for c in categories:
            r = self._req('GET', f'/video/list/{c}')
            ok = r['ok'] and isinstance(r['body'], list)
            self._log(f'/video/list/{c}', 'list videos', ok, f"code={r['code']}")
        r_bad = self._req('GET', '/video/list/invalid_category', expected=404)
        self._log('/video/list/invalid_category', 'invalid category', r_bad['ok'], f"code={r_bad['code']}")

    def test_video_housing_type_lists(self):
        for ht in ['oval','sqaure','angular']:
            r = self._req('GET', f'/video/housing_types/{ht}')
            ok = r['ok'] and isinstance(r['body'], list)
            self._log(f'/video/housing_types/{ht}', 'housing type videos', ok, f"code={r['code']}")
        r_invalid = self._req('GET', '/video/housing_types/bad', expected=400)
        self._log('/video/housing_types/bad', 'invalid housing type', r_invalid['ok'], f"code={r_invalid['code']}")

    def test_product_exists(self):
        for mt in ['shaft','housing']:
            r = self._req('GET', '/product_exists', params={'product_id': 'NON_EXIST_X', 'measurement_type': mt})
            ok = r['ok'] and isinstance(r['body'], dict) and r['body'].get('exists') is False
            self._log('/product_exists', f'non-existent {mt}', ok, f"code={r['code']}")
        r_missing = self._req('GET', '/product_exists', expected=422)
        self._log('/product_exists', 'missing params', r_missing['ok'], f"code={r_missing['code']}")
        r_bad = self._req('GET', '/product_exists', params={'product_id':'X','measurement_type':'bad'}, expected=400)
        self._log('/product_exists', 'invalid measurement_type', r_bad['ok'], f"code={r_bad['code']}")

    def test_shaft_measurements(self):
        ts = int(time.time())
        pid = f'FT_SHAFT_{ts}'
        payload = {'product_id': pid,'roll_number': f'ROLL_{ts}','shaft_height': 25.5,'shaft_radius': 12.3}
        r = self._req('POST', '/shaft_measurement', data=payload)
        self._log('/shaft_measurement', 'insert shaft', r['ok'], f"code={r['code']}")
        dup = self._req('POST', '/shaft_measurement', data=payload, expected=409)
        self._log('/shaft_measurement', 'duplicate shaft pid', dup['ok'], f"code={dup['code']}")
        bad = self._req('POST', '/shaft_measurement', data={'product_id': f'BAD_SHAFT_{ts}'}, expected=400)
        self._log('/shaft_measurement', 'missing fields', bad['ok'], f"code={bad['code']}")
        self.last_shaft_pid = pid if r['ok'] else None

    def test_housing_measurements(self):
        ts = int(time.time())
        base_pid = f'FT_HOUSING_{ts}'
        for i, ht in enumerate(['housing','oval','sqaure','angular']):
            pid = f'{base_pid}_{i}'
            data = {'product_id': pid,'roll_number': f'ROLL_{ts}_{i}','housing_type': ht,'housing_height': 30+i,'housing_radius':10+i,'housing_depth':5+i}
            r = self._req('POST','/housing_measurement', data=data)
            self._log('/housing_measurement', f'insert {ht}', r['ok'], f"code={r['code']}")
            if i == 0 and r['ok']:
                self.last_housing_pid = pid
        dup = self._req('POST','/housing_measurement', data={'product_id': f'{base_pid}_0','roll_number':'R','housing_type':'housing','housing_height':10,'housing_radius':5,'housing_depth':2}, expected=409)
        self._log('/housing_measurement', 'duplicate pid', dup['ok'], f"code={dup['code']}")
        bad_type = self._req('POST','/housing_measurement', data={'product_id': f'{base_pid}_BAD','roll_number':'R','housing_type':'bad','housing_height':10,'housing_radius':5,'housing_depth':2}, expected=400)
        self._log('/housing_measurement', 'invalid housing_type', bad_type['ok'], f"code={bad_type['code']}")
        missing = self._req('POST','/housing_measurement', data={'product_id': f'{base_pid}_MISS','roll_number':'R','housing_height':10,'housing_radius':5,'housing_depth':2}, expected=400)
        self._log('/housing_measurement', 'missing required', missing['ok'], f"code={missing['code']}")

    def test_measured_units(self):
        r = self._req('GET', '/measured_units/NON_EXIST_ROLL')
        ok = r['ok'] and isinstance(r['body'], dict) and r['body'].get('shaft_measurements') == []
        self._log('/measured_units/{roll_number}', 'non-existent roll', ok, f"code={r['code']}")

    def test_schema(self):
        r = self._req('GET','/db/schema/tables')
        ok = r['ok'] and isinstance(r['body'], dict) and {'measured_shafts','measured_housings','user_entry'}.issubset(set(r['body'].get('tables',[])))
        self._log('/db/schema/tables','list tables', ok, f"code={r['code']}")
        desc = self._req('GET','/db/schema/tables/measured_housings')
        okd = desc['ok'] and isinstance(desc['body'], dict) and desc['body'].get('table') == 'measured_housings'
        self._log('/db/schema/tables/measured_housings','describe housing', okd, f"code={desc['code']}")

    def test_generic_queries(self):
        # Only if we previously inserted
        if not self.last_shaft_pid:
            return
        sel = self._req('POST','/db/query/select', data={'table':'measured_shafts','filters':{'product_id': self.last_shaft_pid},'limit':1})
        ok_sel = sel['ok'] and sel['body'].get('count') == 1
        self._log('/db/query/select','select shaft', ok_sel, f"code={sel['code']}")
        upd = self._req('POST','/db/query/update', data={'table':'measured_shafts','set':{'shaft_height': 77.7},'filters':{'product_id': self.last_shaft_pid}})
        ok_upd = upd['ok'] and upd['body'].get('updated') == 1
        self._log('/db/query/update','update shaft', ok_upd, f"code={upd['code']}")

    def test_video_streaming(self):
        head = self._req('HEAD', '/video/shaft/shaft_height.mkv', expected=200)  # may 200 if exists else modify expected
        if head['code'] not in (200,404):
            self._log('/video/{category}/{filename}', 'HEAD video', False, f"code={head['code']}")
        else:
            self._log('/video/{category}/{filename}', 'HEAD video', True, f"code={head['code']}")
        bad_cat = self._req('GET','/video/invalid_cat/file.mkv', expected=404)
        self._log('/video/invalid_cat/file.mkv','invalid category', bad_cat['ok'], f"code={bad_cat['code']}")

    def test_user_session_workflow(self):
        rn = f'USR_{int(time.time())}_{random.randint(100,999)}'
        r_create = self._req('POST','/user_entry', data={'roll_number': rn, 'name':'Func User'})
        self._log('/user_entry','create session', r_create['ok'], f"code={r_create['code']}")
        if not r_create['ok'] or not isinstance(r_create['body'], dict):
            return
        sid = r_create['body'].get('session_id')
        if not sid:
            self._log('/user_entry','missing session id', False, 'no session_id returned')
            return
        should = self._req('GET','/user_entry/should_calibrate', params={'roll_number': rn})
        self._log('/user_entry/should_calibrate','should calibrate check', should['ok'], f"code={should['code']}")
        complete = self._req('POST','/user_entry/complete_calibration', data={'session_id': sid})
        self._log('/user_entry/complete_calibration','complete calibration', complete['ok'], f"code={complete['code']}")
        repeat = self._req('POST','/user_entry/complete_calibration', data={'session_id': sid})
        self._log('/user_entry/complete_calibration','repeat completion idempotent', repeat['ok'], f"code={repeat['code']}")

    def run(self):
        self.test_root()
        self.test_housing_types()
        self.test_video_lists()
        self.test_video_housing_type_lists()
        self.test_product_exists()
        self.test_shaft_measurements()
        self.test_housing_measurements()
        self.test_measured_units()
        self.test_schema()
        self.test_generic_queries()
        self.test_video_streaming()
        self.test_user_session_workflow()
        return {'passed': self.passed, 'failed': self.failed, 'total': self.passed + self.failed, 'results': self.test_results}

############################################################
# Network + Load Tester (subset of load_test with improvements)
############################################################

class LoadTester:
    def __init__(self, base_url: str, concurrency: int, requests_count: int):
        self.base_url = base_url
        self.concurrency = concurrency
        self.requests_count = requests_count
        self.shaft_ids: List[str] = []
        self.housing_ids: List[str] = []
        self.phase1_results: List[Dict[str, Any]] = []
        self.phase2_results: List[Dict[str, Any]] = []

    # ---------------- network diagnostics -----------------
    def dns_resolution(self) -> Dict[str, Any]:
        try:
            host = urlparse(self.base_url).hostname or 'localhost'
            start = time.time()
            ip = socket.gethostbyname(host)
            dur = (time.time() - start) * 1000
            print(f"DNS: {host} -> {ip} in {dur:.2f}ms")
            return {'success': True, 'ip': ip, 'ms': dur}
        except Exception as e:
            print(f"DNS failed: {e}")
            return {'success': False, 'error': str(e)}

    def tcp_connect(self) -> Dict[str, Any]:
        try:
            p = urlparse(self.base_url)
            host = p.hostname or 'localhost'
            port = p.port or (443 if p.scheme == 'https' else 80)
            start = time.time()
            s = socket.create_connection((host, port), timeout=5)
            s.close()
            dur = (time.time() - start) * 1000
            print(f"TCP: {host}:{port} {dur:.2f}ms")
            return {'success': True, 'ms': dur}
        except Exception as e:
            print(f"TCP failed: {e}")
            return {'success': False, 'error': str(e)}

    async def ssl_handshake(self) -> Dict[str, Any]:
        if not self.base_url.startswith('https://'):
            return {'success': True, 'ms': 0, 'note': 'http'}
        try:
            host = urlparse(self.base_url).hostname or 'localhost'
            start = time.time()
            ctx = ssl.create_default_context()
            sock = socket.create_connection((host, 443), timeout=5)
            ssock = ctx.wrap_socket(sock, server_hostname=host)
            ssock.close()
            dur = (time.time() - start) * 1000
            print(f"SSL: {dur:.2f}ms")
            return {'success': True, 'ms': dur}
        except Exception as e:
            print(f"SSL failed: {e}")
            return {'success': False, 'error': str(e)}

    async def baseline_latency(self) -> Dict[str, Any]:
        lat = []
        for i in range(5):
            start = time.time()
            try:
                requests.get(f"{self.base_url}/", timeout=10)
                lat.append((time.time() - start) * 1000)
            except Exception:
                pass
        if not lat:
            return {'success': False}
        return {
            'success': True,
            'avg_ms': statistics.mean(lat),
            'min_ms': min(lat),
            'max_ms': max(lat),
            'jitter_ms': max(lat) - min(lat)
        }

    # ---------------- helper (aiohttp) -----------------
    async def _ensure_aiohttp(self):  # pragma: no cover
        if aiohttp is None:
            raise RuntimeError('aiohttp not installed. pip install aiohttp')

    async def _request(self, session, spec: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        url = f"{self.base_url}{spec['endpoint']}"
        method = spec['method']
        try:
            if method == 'GET':
                async with session.get(url, params=spec.get('params')) as r:
                    await r.text()
                    code = r.status
            elif method == 'POST':
                async with session.post(url, json=spec.get('data')) as r:
                    await r.text()
                    code = r.status
            else:
                code = 0
        except Exception as e:
            return {'endpoint': spec.get('endpoint'), 'success': False, 'error': str(e), 'rt': time.time() - start}
        rt = time.time() - start
        expected = spec.get('expected')
        if expected is not None:
            ok = code == expected
        else:
            ok = code < 400
        return {
            'endpoint': spec.get('endpoint'),
            'success': ok,
            'status': code,
            'expected': expected,
            'rt': rt,
            '_type': spec.get('_type'),
            '_pid': spec.get('_pid')
        }

    def _build_phase1_specs(self) -> List[Dict[str, Any]]:
        """Generate a mixture of valid and intentional invalid requests.

        Intentional invalid cases (expected failures):
          - Missing shaft fields (400)
          - Invalid housing_type (400)
          - Duplicate shaft/housing insert (409) immediately after a valid insert
          - Invalid measurement_type for product_exists (400)
        """
        specs: List[Dict[str, Any]] = []
        last_inserted_shaft_pid = None
        last_inserted_housing_pid = None
        for i in range(self.requests_count):
            mod = i % 6
            ts = int(time.time() * 1000)
            rnd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if mod == 0:  # root or housing_types alternating
                if i % 2 == 0:
                    specs.append({'endpoint': '/', 'method': 'GET'})
                else:
                    specs.append({'endpoint': '/housing_types', 'method': 'GET'})
            elif mod == 1:  # valid shaft insert + duplicate every 15th
                pid = f"L_SHAFT_{ts}_{rnd}"
                shaft_spec = {'endpoint': '/shaft_measurement', 'method': 'POST', '_pid': pid, '_type': 'shaft', 'data': {
                    'product_id': pid,
                    'roll_number': f'ROLL_{ts}',
                    'shaft_height': round(random.uniform(10,40),2),
                    'shaft_radius': round(random.uniform(5,25),2)
                }}
                specs.append(shaft_spec)
                last_inserted_shaft_pid = pid
                if i % 15 == 0:  # duplicate expected 409
                    specs.append({'endpoint': '/shaft_measurement', 'method': 'POST', 'data': shaft_spec['data'], 'expected': 409})
            elif mod == 2:  # invalid shaft (missing radius) every 10th
                pid = f"BAD_SHAFT_{ts}_{rnd}"
                specs.append({'endpoint': '/shaft_measurement', 'method': 'POST', 'data': {
                    'product_id': pid,
                    'roll_number': f'ROLL_{ts}',
                    'shaft_height': round(random.uniform(10,40),2)
                }, 'expected': 400})
            elif mod == 3:  # valid housing insert + duplicate
                pid = f"L_HOUSING_{ts}_{rnd}"
                housing_spec = {'endpoint': '/housing_measurement', 'method': 'POST', '_pid': pid, '_type': 'housing', 'data': {
                    'product_id': pid,
                    'roll_number': f'ROLL_{ts}',
                    'housing_type': random.choice(['housing','oval','sqaure','angular']),
                    'housing_height': round(random.uniform(10,50),2),
                    'housing_radius': round(random.uniform(5,25),2),
                    'housing_depth': round(random.uniform(1,10),2)
                }}
                specs.append(housing_spec)
                last_inserted_housing_pid = pid
                if i % 20 == 0:
                    specs.append({'endpoint': '/housing_measurement', 'method': 'POST', 'data': housing_spec['data'], 'expected': 409})
            elif mod == 4:  # invalid housing type
                pid = f"BAD_HOUSING_{ts}_{rnd}"
                specs.append({'endpoint': '/housing_measurement', 'method': 'POST', 'data': {
                    'product_id': pid,
                    'roll_number': f'ROLL_{ts}',
                    'housing_type': 'bad',
                    'housing_height': 10.0,
                    'housing_radius': 5.0,
                    'housing_depth': 2.0
                }, 'expected': 400})
            else:  # product_exists mixture
                if i % 12 == 0:
                    specs.append({'endpoint': '/product_exists', 'method': 'GET', 'params': {'product_id': 'X','measurement_type':'bad'}, 'expected': 400})
                else:
                    specs.append({'endpoint': '/product_exists', 'method': 'GET', 'params': {'product_id': f'NO_{rnd}', 'measurement_type': random.choice(['shaft','housing'])}})
        return specs

    async def phase1(self):
        await self._ensure_aiohttp()
        specs = self._build_phase1_specs()
        connector = aiohttp.TCPConnector(limit=self.concurrency, keepalive_timeout=15)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            results = await asyncio.gather(*[self._request(session, s) for s in specs], return_exceptions=True)
        fail_counts: Dict[str,int] = {}
        for spec, res in zip(specs, results):
            if isinstance(res, dict) and res.get('success'):
                if spec.get('_type') == 'shaft':
                    self.shaft_ids.append(spec.get('_pid'))
                if spec.get('_type') == 'housing':
                    self.housing_ids.append(spec.get('_pid'))
            else:
                ep = spec.get('endpoint')
                fail_counts[ep] = fail_counts.get(ep,0)+1
        self.phase1_results = [r for r in results if isinstance(r, dict)]
        ok = sum(1 for r in self.phase1_results if r.get('success'))
        total = len(self.phase1_results)
        rts = [r['rt'] for r in self.phase1_results if r.get('success')]
        summary = {
            'total': total,
            'ok': ok,
            'fail': total - ok,
            'avg_rt': statistics.mean(rts) if rts else None,
            'min_rt': min(rts) if rts else None,
            'max_rt': max(rts) if rts else None,
            'p95_rt': (statistics.quantiles(rts, n=20)[18] if len(rts) >= 20 else (max(rts) if rts else None)),
            'fail_by_endpoint': fail_counts
        }
        print("Phase 1: load inserts & baseline")
        print(json.dumps(summary, indent=2))
        return summary

    async def phase2(self):
        await self._ensure_aiohttp()
        specs: List[Dict[str,Any]] = [
            {'endpoint': '/db/schema/tables', 'method': 'GET'},
            {'endpoint': '/db/schema/tables/measured_shafts', 'method': 'GET'},
            {'endpoint': '/db/schema/tables/measured_housings', 'method': 'GET'}
        ]
        for pid in self.shaft_ids[:2]:
            specs.append({'endpoint': '/db/query/select', 'method': 'POST', 'data': {'table': 'measured_shafts', 'filters': {'product_id': pid}, 'limit':1}})
        for pid in self.housing_ids[:2]:
            specs.append({'endpoint': '/db/query/select', 'method': 'POST', 'data': {'table': 'measured_housings', 'filters': {'product_id': pid}, 'limit':1}})
        # User session mini flow
        user_rn = f"LROLL_{int(time.time())}_{random.randint(100,999)}"
        specs.append({'endpoint': '/user_entry', 'method': 'POST', 'data': {'roll_number': user_rn, 'name': 'Combined Load User'}})
        connector = aiohttp.TCPConnector(limit=10, keepalive_timeout=15)
        timeout = aiohttp.ClientTimeout(total=40)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            results = await asyncio.gather(*[self._request(session, s) for s in specs], return_exceptions=True)
        self.phase2_results = [r for r in results if isinstance(r, dict)]
        ok = sum(1 for r in self.phase2_results if r.get('success'))
        total = len(self.phase2_results)
        print("Phase 2: generic queries & schema")
        print(f"Succeeded {ok}/{total}")
        return {'total': total, 'ok': ok, 'fail': total-ok}

############################################################
# Combined Orchestrator
############################################################

class CombinedRunner:
    def __init__(self, base_url: str, concurrency: int, requests_count: int, skip_functional: bool, skip_load: bool, json_out: Optional[str]):
        self.base_url = base_url
        self.concurrency = concurrency
        self.requests_count = requests_count
        self.skip_functional = skip_functional
        self.skip_load = skip_load
        self.json_out = json_out
        self.functional_summary: Dict[str,Any] | None = None
        self.network_metrics: Dict[str,Any] | None = None
        self.phase1_summary: Dict[str,Any] | None = None
        self.phase2_summary: Dict[str,Any] | None = None

    async def run(self):
        print(f"Base URL: {self.base_url}")
        # Functional tests
        if not self.skip_functional:
            print("\n== Functional Endpoint Tests ==")
            ft = FunctionalTester(self.base_url)
            self.functional_summary = ft.run()
        # Network diagnostics
        print("\n== Network Diagnostics ==")
        lt = LoadTester(self.base_url, self.concurrency, self.requests_count)
        dns = lt.dns_resolution()
        tcp = lt.tcp_connect()
        ssl_res = await lt.ssl_handshake()
        base_lat = await lt.baseline_latency()
        self.network_metrics = {'dns': dns, 'tcp': tcp, 'ssl': ssl_res, 'latency': base_lat}
        # Load Phases
        if not self.skip_load:
            print("\n== Load Phase 1 ==")
            self.phase1_summary = await lt.phase1()
            print("\n== Load Phase 2 ==")
            self.phase2_summary = await lt.phase2()
        # Aggregate
        combined = {
            'base_url': self.base_url,
            'functional': self.functional_summary,
            'network': self.network_metrics,
            'phase1': self.phase1_summary,
            'phase2': self.phase2_summary,
            'timestamp': int(time.time())
        }
        print("\n== Summary ==")
        print(json.dumps(combined, indent=2))
        if self.json_out:
            with open(self.json_out, 'w') as f:
                json.dump(combined, f, indent=2)
            print(f"Results saved to {self.json_out}")

############################################################
# CLI Entrypoint
############################################################

def main():
    parser = argparse.ArgumentParser(description='Combined functional + network + load tester')
    parser.add_argument('--url', default='http://127.0.0.1:5000', help='Base API URL')
    parser.add_argument('--requests', type=int, default=50, help='Number of phase1 load requests')
    parser.add_argument('--concurrency', type=int, default=20, help='Concurrency for load phase1')
    parser.add_argument('--skip-functional', action='store_true', help='Skip functional endpoint tests')
    parser.add_argument('--skip-load', action='store_true', help='Skip load phases')
    parser.add_argument('--json-out', help='Write combined JSON report to file')
    args = parser.parse_args()
    base_url = normalize_base_url(args.url)
    runner = CombinedRunner(base_url, args.concurrency, args.requests, args.skip_functional, args.skip_load, args.json_out)
    asyncio.run(runner.run())

if __name__ == '__main__':
    main()
