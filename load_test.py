import asyncio
import time
import random
import string
import requests
import statistics
import socket
import ssl
from typing import Dict, List
import re
from urllib.parse import urlparse

try:
    import aiohttp
except ImportError:  # fallback to provide clearer message later
    aiohttp = None  # type: ignore


class HostedAPITester:
    def __init__(self, base_url: str):
        self.base_url = self._normalize_base_url(base_url)
        self.results = []
        self.concurrent_requests = 20
        self.shaft_ids = []
        self.housing_ids = []

    def _require_aiohttp(self):
        if aiohttp is None:
            raise RuntimeError("aiohttp is required. Install with: pip install aiohttp")

    def _normalize_base_url(self, raw: str) -> str:
        raw = raw.strip()
        # Handle cases like http:127.0.0.1:5000 (missing //)
        if raw.startswith('http:') and not raw.startswith('http://'):
            raw = raw.replace('http:', '', 1)
        if raw.startswith('https:') and not raw.startswith('https://'):
            raw = raw.replace('https:', '', 1)
        raw = raw.lstrip('/')
        # If no scheme present add http (not https) for localhost patterns
        if not re.match(r'^https?://', raw):
            raw = 'http://' + raw
        parsed = urlparse(raw)
        host = parsed.hostname or 'localhost'
        port = parsed.port
        scheme = parsed.scheme
        netloc = host if port is None else f"{host}:{port}"
        # Rebuild without path/query to keep base clean
        return f"{scheme}://{netloc}".rstrip('/')

    def ping_server(self) -> Dict:
        print("Testing network connectivity (TCP connect)...")
        try:
            parsed = urlparse(self.base_url if '://' in self.base_url else 'http://' + self.base_url)
            host = parsed.hostname or 'localhost'
            scheme = parsed.scheme or 'http'
            port = parsed.port or (443 if scheme == 'https' else 80)
            start_time = time.time()
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            elapsed = (time.time() - start_time) * 1000
            print(f"TCP connect to {host}:{port} took {elapsed:.2f}ms")
            return {"success": True, "ping_ms": elapsed, "host": host, "port": port}
        except Exception as e:
            print(f"Network connectivity failed: {e}")
            return {"success": False, "error": str(e)}

    async def test_ssl_handshake(self) -> Dict:
        if not self.base_url.startswith('https://'):
            return {"success": True, "ssl_time_ms": 0, "message": "HTTP - no SSL"}
        print("Testing SSL handshake...")
        try:
            hostname = self.base_url.replace('https://', '').split('/')[0].split(':')[0]
            start_time = time.time()
            context = ssl.create_default_context()
            sock = socket.create_connection((hostname, 443), timeout=10)
            ssock = context.wrap_socket(sock, server_hostname=hostname)
            ssock.close()
            ssl_time = (time.time() - start_time) * 1000
            print(f"SSL handshake: {ssl_time:.2f}ms")
            return {"success": True, "ssl_time_ms": ssl_time}
        except Exception as e:
            print(f"SSL handshake failed: {e}")
            return {"success": False, "error": str(e)}

    def test_dns_resolution(self) -> Dict:
        print("Testing DNS resolution...")
        try:
            hostname = self.base_url.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
            start_time = time.time()
            ip = socket.gethostbyname(hostname)
            dns_time = (time.time() - start_time) * 1000
            print(f"DNS resolution: {dns_time:.2f}ms (IP: {ip})")
            return {"success": True, "dns_time_ms": dns_time, "ip": ip}
        except Exception as e:
            print(f"DNS resolution failed: {e}")
            return {"success": False, "error": str(e)}

    async def test_geographic_latency(self):
        print("Testing geographic latency...")
        latencies = []
        for i in range(5):
            start_time = time.time()
            try:
                requests.get(f"{self.base_url}/", timeout=10)
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                print(f"  Request {i+1}: {latency:.2f}ms")
            except Exception as e:
                print(f"  Request {i+1}: FAILED - {e}")
        if latencies:
            avg_latency = statistics.mean(latencies)
            print("Latency Summary:")
            print(f"  Average: {avg_latency:.2f}ms")
            print(f"  Min: {min(latencies):.2f}ms")
            print(f"  Max: {max(latencies):.2f}ms")
            print(f"  Jitter: {max(latencies) - min(latencies):.2f}ms")

    async def test_hosted_load_capacity(self, num_requests: int = 100, sequential: bool = False):
        self._require_aiohttp()
        print(f"Phase 1: baseline & inserts ({num_requests} requests)...")
        # build request list
        def build_requests() -> List[Dict]:
            reqs: List[Dict] = []
            for i in range(num_requests):
                timestamp = int(time.time() * 1000)
                rnd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                mod = i % 5
                if mod == 0:
                    reqs.append({"endpoint": "/", "method": "GET"})
                elif mod == 1:
                    reqs.append({"endpoint": "/housing_types", "method": "GET"})
                elif mod == 2:
                    shaft_pid = f"LOAD_SHAFT_{timestamp}_{rnd}"
                    shaft_data = {
                        "product_id": shaft_pid,
                        "roll_number": f"ROLL_{timestamp}",
                        "shaft_height": round(random.uniform(10.0, 50.0), 2),
                        "shaft_radius": round(random.uniform(5.0, 25.0), 2)
                    }
                    reqs.append({"endpoint": "/shaft_measurement", "method": "POST", "data": shaft_data, "_pid": shaft_pid, "_type": "shaft"})
                elif mod == 3:
                    housing_pid = f"LOAD_HOUSING_{timestamp}_{rnd}"
                    housing_data = {
                        "product_id": housing_pid,
                        "roll_number": f"ROLL_{timestamp}",
                        "housing_type": random.choice(["housing", "oval", "sqaure", "angular"]),
                        "housing_height": round(random.uniform(10.0, 50.0), 2),
                        "housing_radius": round(random.uniform(5.0, 25.0), 2),
                        "housing_depth": round(random.uniform(1.0, 10.0), 2)
                    }
                    reqs.append({"endpoint": "/housing_measurement", "method": "POST", "data": housing_data, "_pid": housing_pid, "_type": "housing"})
                else:
                    reqs.append({"endpoint": "/product_exists", "method": "GET", "params": {"product_id": f"NOPE_{rnd}", "measurement_type": random.choice(["shaft", "housing"])}})
            return reqs

        requests_data = build_requests()
        connector = aiohttp.TCPConnector(limit=self.concurrent_requests, keepalive_timeout=30, enable_cleanup_closed=True)
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        endpoint_fail_counts: Dict[str, int] = {}
        first_errors: List[Dict] = []
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            if sequential:
                results = []
                for rd in requests_data:
                    res = await self.make_hosted_request(session, rd)
                    results.append(res)
            else:
                print("  Executing phase 1 requests (concurrent)...")
                results = await asyncio.gather(*[self.make_hosted_request(session, rd) for rd in requests_data], return_exceptions=True)
            successful, failed = [], []
            for rd, result in zip(requests_data, results):
                if isinstance(result, Exception):
                    failed.append({"error": str(result), "endpoint": rd.get('endpoint')})
                    endpoint_fail_counts[rd.get('endpoint','?')] = endpoint_fail_counts.get(rd.get('endpoint','?'),0)+1
                    if len(first_errors) < 5:
                        first_errors.append({"endpoint": rd.get('endpoint'), "error": str(result)})
                    continue
                if result.get("success"):
                    successful.append(result)
                    if rd.get("_type") == "shaft":
                        self.shaft_ids.append(rd.get("_pid"))
                    elif rd.get("_type") == "housing":
                        self.housing_ids.append(rd.get("_pid"))
                else:
                    failed.append(result)
                    ep = rd.get('endpoint')
                    endpoint_fail_counts[ep] = endpoint_fail_counts.get(ep,0)+1
                    if len(first_errors) < 5:
                        first_errors.append({"endpoint": ep, "status": result.get('status_code')})
            print("\nPhase 1 Performance:")
            total = len(results)
            print(f"  Total Requests: {total}")
            print(f"  Successful: {len(successful)} ({(len(successful)/total*100):.1f}%)")
            print(f"  Failed: {len(failed)} ({(len(failed)/total*100):.1f}%)")
            if successful:
                rt = [r["response_time"] for r in successful if r.get("response_time") is not None]
                if rt:
                    avg, mn, mx = statistics.mean(rt), min(rt), max(rt)
                    p95 = statistics.quantiles(rt, n=20)[18] if len(rt) >= 20 else mx
                    print(f"  Average: {avg:.3f}s | Min: {mn:.3f}s | Max: {mx:.3f}s | P95: {p95:.3f}s")
            if endpoint_fail_counts:
                print("  Failures by endpoint:")
                for ep, cnt in endpoint_fail_counts.items():
                    print(f"    {ep}: {cnt}")
            if first_errors:
                print("  First errors sample:")
                for fe in first_errors:
                    print(f"    {fe}")
            await self.test_generic_query_phase(session)

    async def test_generic_query_phase(self, session):
        print("\nPhase 2: extended schema/query & user session tests")
        # Concurrent independent tasks first
        schema_tasks = [
            {"endpoint": "/db/schema/tables", "method": "GET"},
            {"endpoint": "/db/schema/tables/measured_shafts", "method": "GET"},
            {"endpoint": "/db/schema/tables/measured_housings", "method": "GET"},
        ]
        # Sample product IDs captured in phase 1
        sample_shaft = self.shaft_ids[:2]
        sample_housing = self.housing_ids[:2]
        for pid in sample_shaft:
            schema_tasks.append({
                "endpoint": "/db/query/select",
                "method": "POST",
                "data": {"table": "measured_shafts", "columns": ["product_id", "shaft_height", "roll_number"], "filters": {"product_id": pid}, "limit": 1},
                "capture_json": True
            })
            schema_tasks.append({
                "endpoint": "/db/query/update",
                "method": "POST",
                "data": {"table": "measured_shafts", "set": {"shaft_height": round(random.uniform(60, 80), 2)}, "filters": {"product_id": pid}}
            })
        for pid in sample_housing:
            schema_tasks.append({
                "endpoint": "/db/query/select",
                "method": "POST",
                "data": {"table": "measured_housings", "columns": ["product_id", "housing_radius", "roll_number"], "filters": {"product_id": pid}, "limit": 1},
                "capture_json": True
            })
            schema_tasks.append({
                "endpoint": "/db/query/update",
                "method": "POST",
                "data": {"table": "measured_housings", "set": {"housing_radius": round(random.uniform(30, 40), 2)}, "filters": {"product_id": pid}}
            })

        # Execute concurrent tasks
        concurrent_results = await asyncio.gather(*[self.make_hosted_request(session, t) for t in schema_tasks], return_exceptions=True)
        # Collect roll_numbers for measured_units aggregation
        roll_numbers = set()
        for res in concurrent_results:
            if isinstance(res, dict) and res.get("json") and isinstance(res.get("json").get("data"), list):
                data = res["json"].get("data")
                if data:
                    rn = data[0].get("roll_number")
                    if rn:
                        roll_numbers.add(rn)

        # Dependent sequential tasks (measured_units & user session flow)
        sequential_specs = []
        for rn in list(roll_numbers)[:2]:
            sequential_specs.append({"endpoint": f"/measured_units/{rn}", "method": "GET"})

        # User session workflow
        user_rn = f"UROLL_{int(time.time())}_{random.randint(100,999)}"
        user_name = "Load Test User"
        sequential_specs.append({"endpoint": "/user_entry", "method": "POST", "data": {"roll_number": user_rn, "name": user_name}, "capture_json": True})
        # We'll dynamically append calibration completion once we have session id

        sequential_results = []
        for spec in sequential_specs:
            r = await self.make_hosted_request(session, spec)
            sequential_results.append(r)
            # If this is the new user entry, schedule calibration endpoints
            if spec["endpoint"] == "/user_entry" and isinstance(r, dict) and r.get("json"):
                session_id = r["json"].get("session_id")
                if session_id:
                    should_calib_spec = {"endpoint": "/user_entry/should_calibrate", "method": "GET", "params": {"roll_number": user_rn}}
                    complete_spec = {"endpoint": "/user_entry/complete_calibration", "method": "POST", "data": {"session_id": session_id}, "capture_json": True}
                    status_spec = {"endpoint": f"/user_entry/session/{session_id}", "method": "GET", "capture_json": True}
                    for follow in (should_calib_spec, complete_spec, status_spec):
                        fr = await self.make_hosted_request(session, follow)
                        sequential_results.append(fr)

        # Summaries
        def _count_ok(res_list):
            return sum(1 for r in res_list if isinstance(r, dict) and r.get("success"))
        conc_ok = _count_ok(concurrent_results)
        seq_ok = _count_ok(sequential_results)
        print(f"  Concurrent generic tasks: {conc_ok}/{len(concurrent_results)} succeeded")
        print(f"  Sequential dependent tasks: {seq_ok}/{len(sequential_results)} succeeded")
        # Highlight calibration completion result
        calib = next((r for r in sequential_results if isinstance(r, dict) and r.get("endpoint") == "/user_entry/complete_calibration"), None)
        if calib and calib.get("success"):
            print("  User calibration workflow: success")
        elif calib:
            print(f"  User calibration workflow failed (status={calib.get('status_code')})")

    async def make_hosted_request(self, session, req_data: Dict) -> Dict:
        start_time = time.time()
        try:
            url = f"{self.base_url}{req_data['endpoint']}"
            if req_data["method"] == "GET":
                async with session.get(url, params=req_data.get("params")) as response:
                    txt = await response.text()
                    status_code = response.status
                    body_json = None
                    if req_data.get("capture_json"):
                        try:
                            body_json = await response.json(content_type=None)
                        except Exception:
                            body_json = None
            elif req_data["method"] == "POST":
                async with session.post(url, json=req_data.get("data")) as response:
                    txt = await response.text()
                    status_code = response.status
                    body_json = None
                    if req_data.get("capture_json"):
                        try:
                            body_json = await response.json(content_type=None)
                        except Exception:
                            body_json = None
            else:
                status_code = 0
            end_time = time.time()
            return {
                "endpoint": req_data["endpoint"],
                "method": req_data["method"],
                "status_code": status_code,
                "response_time": end_time - start_time,
                "success": status_code < 400 if status_code else False,
                "timestamp": start_time,
                "json": body_json if req_data.get("capture_json") else None
            }
        except Exception as e:
            end_time = time.time()
            return {
                "endpoint": req_data.get("endpoint"),
                "method": req_data.get("method"),
                "status_code": None,
                "response_time": end_time - start_time,
                "success": False,
                "timestamp": start_time,
                "error": str(e)
            }

    async def comprehensive_hosted_test(self):
        print("HOSTED API COMPREHENSIVE TEST")
        print("=" * 50)
        self.test_dns_resolution()
        self.ping_server()
        await self.test_ssl_handshake()
        print()
        await self.test_geographic_latency()
        print()
        await self.test_hosted_load_capacity(100)
        print("\nPerformance Comparison:")
        print("  Local API: Test with your original load_test.py for baseline")
        print("  Hosted API: Results above")
        print("  Expected: Hosted will be slower due to network latency")
        print("  Good hosted performance: <500ms average response time")
        print("  Excellent hosted performance: <200ms average response time")


if __name__ == "__main__":
    print("Hosted API Testing Tool (supports localhost)")
    print("=" * 30)
    hosted_url = input("Enter API URL (e.g. http://127.0.0.1:5000 or https://your-app): ").strip()
    if not hosted_url:
        print("No URL provided!")
        raise SystemExit(1)
    tester = HostedAPITester(hosted_url)
    print(f"Testing: {tester.base_url}")
    asyncio.run(tester.comprehensive_hosted_test())