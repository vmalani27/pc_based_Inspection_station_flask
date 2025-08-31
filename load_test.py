import asyncio
import aiohttp
import time
import json
import requests
import random
import string
from typing import List, Dict
import statistics
import socket
import ssl

class HostedAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.results = []
        self.concurrent_requests = 20  # Lower for hosted APIs
        
    def ping_server(self) -> Dict:
        """Test basic connectivity and measure network latency"""
        print("🏓 Testing network connectivity...")
        
        try:
            # Extract hostname from URL
            hostname = self.base_url.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
            
            # Simple socket ping
            start_time = time.time()
            sock = socket.create_connection((hostname, 80 if 'http://' in self.base_url else 443), timeout=10)
            sock.close()
            ping_time = (time.time() - start_time) * 1000  # Convert to ms
            
            print(f"✅ Network ping: {ping_time:.2f}ms")
            return {"success": True, "ping_ms": ping_time}
            
        except Exception as e:
            print(f"❌ Network connectivity failed: {e}")
            return {"success": False, "error": str(e)}

    async def test_ssl_handshake(self) -> Dict:
        """Test SSL handshake time for HTTPS APIs"""
        if not self.base_url.startswith('https://'):
            return {"success": True, "ssl_time_ms": 0, "message": "HTTP - no SSL"}
        
        print("🔒 Testing SSL handshake...")
        
        try:
            hostname = self.base_url.replace('https://', '').split('/')[0].split(':')[0]
            
            start_time = time.time()
            context = ssl.create_default_context()
            sock = socket.create_connection((hostname, 443), timeout=10)
            ssock = context.wrap_socket(sock, server_hostname=hostname)
            ssock.close()
            ssl_time = (time.time() - start_time) * 1000
            
            print(f"✅ SSL handshake: {ssl_time:.2f}ms")
            return {"success": True, "ssl_time_ms": ssl_time}
            
        except Exception as e:
            print(f"❌ SSL handshake failed: {e}")
            return {"success": False, "error": str(e)}

    def test_dns_resolution(self) -> Dict:
        """Test DNS resolution time"""
        print("🌐 Testing DNS resolution...")
        
        try:
            hostname = self.base_url.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
            
            start_time = time.time()
            ip = socket.gethostbyname(hostname)
            dns_time = (time.time() - start_time) * 1000
            
            print(f"✅ DNS resolution: {dns_time:.2f}ms (IP: {ip})")
            return {"success": True, "dns_time_ms": dns_time, "ip": ip}
            
        except Exception as e:
            print(f"❌ DNS resolution failed: {e}")
            return {"success": False, "error": str(e)}

    async def test_geographic_latency(self):
        """Test latency from different perspectives"""
        print("🌍 Testing geographic latency...")
        
        # Simple HTTP requests to measure total round-trip time
        latencies = []
        
        for i in range(5):
            start_time = time.time()
            try:
                response = requests.get(f"{self.base_url}/", timeout=10)
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                print(f"  Request {i+1}: {latency:.2f}ms")
            except Exception as e:
                print(f"  Request {i+1}: FAILED - {e}")
        
        if latencies:
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            print(f"📊 Latency Summary:")
            print(f"  Average: {avg_latency:.2f}ms")
            print(f"  Min: {min_latency:.2f}ms") 
            print(f"  Max: {max_latency:.2f}ms")
            print(f"  Jitter: {max_latency - min_latency:.2f}ms")

    async def test_hosted_load_capacity(self, num_requests: int = 100):
        """Test hosted API under load (smaller scale than local)"""
        print(f"🚀 Testing hosted API capacity: {num_requests} requests...")
        
        # Generate test data
        requests_data = []
        for i in range(num_requests):
            timestamp = int(time.time() * 1000)
            random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            
            if i % 3 == 0:
                requests_data.append({"endpoint": "/", "method": "GET"})
            elif i % 3 == 1:
                requests_data.append({"endpoint": "/housing_types", "method": "GET"})
            else:
                shaft_data = {
                    "product_id": f"HOSTED_TEST_{timestamp}_{i}_{random_suffix}",
                    "roll_number": f"HOSTED_ROLL_{timestamp}",
                    "shaft_height": round(random.uniform(10.0, 50.0), 2),
                    "shaft_radius": round(random.uniform(5.0, 25.0), 2)
                }
                requests_data.append({
                    "endpoint": "/shaft_measurement",
                    "method": "POST",
                    "data": shaft_data
                })
        
        # Execute requests with hosted-appropriate concurrency
        connector = aiohttp.TCPConnector(
            limit=self.concurrent_requests,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=60, connect=15)  # Longer timeouts for hosted
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            
            for req_data in requests_data:
                task = self.make_hosted_request(session, req_data)
                tasks.append(task)
            
            print("  Executing requests...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            successful = []
            failed = []
            
            for result in results:
                if isinstance(result, Exception):
                    failed.append({"error": str(result)})
                elif result["success"]:
                    successful.append(result)
                else:
                    failed.append(result)
            
            # Analyze hosted performance
            print(f"\n📊 Hosted API Performance:")
            print(f"  Total Requests: {len(results)}")
            print(f"  ✅ Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
            print(f"  ❌ Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
            
            if successful:
                response_times = [r["response_time"] for r in successful]
                avg_time = statistics.mean(response_times)
                min_time = min(response_times)
                max_time = max(response_times)
                p95_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max_time
                
                print(f"  ⏱️  Response Times:")
                print(f"    Average: {avg_time:.3f}s ({avg_time*1000:.0f}ms)")
                print(f"    Min: {min_time:.3f}s ({min_time*1000:.0f}ms)")
                print(f"    Max: {max_time:.3f}s ({max_time*1000:.0f}ms)")
                print(f"    95th percentile: {p95_time:.3f}s ({p95_time*1000:.0f}ms)")
                
                # Calculate throughput
                if results:
                    start_time = min(r["timestamp"] for r in successful)
                    end_time = max(r["timestamp"] for r in successful)
                    duration = max(end_time - start_time, 0.001)
                    rps = len(successful) / duration
                    print(f"  🚀 Throughput: {rps:.2f} requests/second")
            
            # Show error breakdown
            if failed:
                error_types = {}
                for failure in failed:
                    if "status_code" in failure:
                        error_key = f"HTTP {failure['status_code']}"
                    else:
                        error_key = "Connection/Timeout Error"
                    error_types[error_key] = error_types.get(error_key, 0) + 1
                
                print(f"  🔥 Error Breakdown:")
                for error_type, count in error_types.items():
                    print(f"    {error_type}: {count}")

    async def make_hosted_request(self, session: aiohttp.ClientSession, req_data: Dict) -> Dict:
        """Make request optimized for hosted APIs"""
        start_time = time.time()
        
        try:
            url = f"{self.base_url}{req_data['endpoint']}"
            
            if req_data["method"] == "GET":
                async with session.get(url, params=req_data.get("params")) as response:
                    await response.text()  # Read response
                    status_code = response.status
            elif req_data["method"] == "POST":
                async with session.post(url, json=req_data.get("data")) as response:
                    await response.text()  # Read response
                    status_code = response.status
            
            end_time = time.time()
            
            return {
                "endpoint": req_data["endpoint"],
                "method": req_data["method"],
                "status_code": status_code,
                "response_time": end_time - start_time,
                "success": status_code < 400,
                "timestamp": start_time
            }
            
        except Exception as e:
            end_time = time.time()
            return {
                "endpoint": req_data["endpoint"],
                "method": req_data["method"],
                "status_code": None,
                "response_time": end_time - start_time,
                "success": False,
                "timestamp": start_time,
                "error": str(e)
            }

    async def comprehensive_hosted_test(self):
        """Run comprehensive hosted API testing"""
        print("🌐 HOSTED API COMPREHENSIVE TEST")
        print("=" * 50)
        
        # 1. Basic connectivity tests
        dns_result = self.test_dns_resolution()
        ping_result = self.ping_server()
        ssl_result = await self.test_ssl_handshake()
        
        print()
        
        # 2. Latency analysis
        await self.test_geographic_latency()
        
        print()
        
        # 3. Load testing (smaller scale for hosted)
        await self.test_hosted_load_capacity(100)
        
        # 4. Compare with local performance
        print(f"\n🔄 Performance Comparison:")
        print(f"  Local API: Test with your load_test.py for baseline")
        print(f"  Hosted API: Results above")
        print(f"  Expected: Hosted will be slower due to network latency")
        print(f"  Good hosted performance: <500ms average response time")
        print(f"  Excellent hosted performance: <200ms average response time")

if __name__ == "__main__":
    print("🌐 Hosted API Testing Tool")
    print("=" * 30)
    
    # Get hosted API URL from user
    hosted_url = input("Enter your hosted API URL (e.g., https://your-api.herokuapp.com): ").strip()
    
    if not hosted_url:
        print("❌ No URL provided!")
        exit(1)
    
    if not hosted_url.startswith(('http://', 'https://')):
        hosted_url = 'https://' + hosted_url
    
    print(f"Testing: {hosted_url}")
    
    tester = HostedAPITester(hosted_url)
    asyncio.run(tester.comprehensive_hosted_test())