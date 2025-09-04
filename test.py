import requests
import json
import os
import time
from typing import Dict, Any, List
import traceback

class APITester:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.test_results: List[Dict[str, Any]] = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.last_shaft_id: str | None = None
        self.last_housing_id: str | None = None

    # ----------------------- helpers -----------------------
    def log_test(self, endpoint: str, test_case: str, status: str, details: str = ""):
        result = {
            "endpoint": endpoint,
            "test_case": test_case,
            "status": status,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        self.total_tests += 1
        if status == "PASS":
            self.passed_tests += 1
            print(f"✅ {endpoint} - {test_case}: PASS")
        else:
            self.failed_tests += 1
            print(f"❌ {endpoint} - {test_case}: FAIL - {details}")

    def make_request(self, method: str, endpoint: str, data: Dict | None = None,
                     files: Dict | None = None, params: Dict | None = None,
                     expected_status: int = 200) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}{endpoint}"
            if method == "GET":
                response = requests.get(url, params=params)
            elif method == "POST":
                if files:
                    response = requests.post(url, files=files, data=data)
                else:
                    response = requests.post(url, json=data)
            elif method == "HEAD":
                response = requests.head(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            return {
                "status_code": response.status_code,
                "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                "success": response.status_code == expected_status
            }
        except Exception as e:
            return {"status_code": None, "response": str(e), "success": False}

    # ----------------------- individual endpoint tests -----------------------
    def test_root_endpoint(self):
        print("\n=== Testing Root Endpoint ===")
        result = self.make_request("GET", "/")
        if result["success"]:
            self.log_test("/", "Root endpoint check", "PASS")
        else:
            self.log_test("/", "Root endpoint check", "FAIL", f"Status: {result['status_code']}")

    def test_housing_types(self):
        print("\n=== Testing Housing Types ===")
        result = self.make_request("GET", "/housing_types")
        if result["success"] and "housing_types" in result["response"]:
            expected = {"oval", "sqaure", "angular"}
            actual = set(result["response"]["housing_types"])
            if expected.issubset(actual):
                self.log_test("/housing_types", "Get housing types", "PASS")
            else:
                self.log_test("/housing_types", "Get housing types", "FAIL", f"Missing: {expected - actual}")
        else:
            self.log_test("/housing_types", "Get housing types", "FAIL", f"Unexpected: {result}")

    def test_video_endpoints(self):
        print("\n=== Testing Video Endpoints ===")
        categories = ["housing", "shaft", "oval_housing", "sqaure_housing", "angular_housing"]
        for c in categories:
            r = self.make_request("GET", f"/video/list/{c}")
            if r["success"] and isinstance(r["response"], list):
                self.log_test(f"/video/list/{c}", f"List videos {c}", "PASS")
            else:
                self.log_test(f"/video/list/{c}", f"List videos {c}", "FAIL", f"Unexpected: {r}")
        r = self.make_request("GET", "/video/list/invalid_category", expected_status=404)
        if r["status_code"] == 404:
            self.log_test("/video/list/invalid", "Invalid category", "PASS")
        else:
            self.log_test("/video/list/invalid", "Invalid category", "FAIL", f"Got: {r['status_code']}")
        for ht in ["oval", "sqaure", "angular"]:
            r = self.make_request("GET", f"/video/housing_types/{ht}")
            if r["success"] and isinstance(r["response"], list):
                self.log_test(f"/video/housing_types/{ht}", "Housing videos", "PASS")
            else:
                self.log_test(f"/video/housing_types/{ht}", "Housing videos", "FAIL", f"Unexpected: {r}")
        r = self.make_request("GET", "/video/housing_types/invalid", expected_status=400)
        if r["status_code"] == 400:
            self.log_test("/video/housing_types/invalid", "Invalid housing type", "PASS")
        else:
            self.log_test("/video/housing_types/invalid", "Invalid housing type", "FAIL", f"Got: {r['status_code']}")

    def test_product_exists(self):
        print("\n=== Testing Product Exists ===")
        for mt in ["shaft", "housing"]:
            r = self.make_request("GET", "/product_exists", params={"product_id": "NONEXISTENT123", "measurement_type": mt})
            if r["success"] and r["response"].get("measurement_type") == mt and r["response"].get("exists") is False:
                self.log_test("/product_exists", f"Non-existent {mt}", "PASS")
            else:
                self.log_test("/product_exists", f"Non-existent {mt}", "FAIL", f"Unexpected: {r}")
        r = self.make_request("GET", "/product_exists", expected_status=422)
        if r["status_code"] == 422:
            self.log_test("/product_exists", "Missing params", "PASS")
        else:
            self.log_test("/product_exists", "Missing params", "FAIL", f"Got: {r['status_code']}")
        r = self.make_request("GET", "/product_exists", params={"product_id": "X", "measurement_type": "bad"}, expected_status=400)
        if r["status_code"] == 400:
            self.log_test("/product_exists", "Invalid measurement type", "PASS")
        else:
            self.log_test("/product_exists", "Invalid measurement type", "FAIL", f"Got: {r['status_code']}")

    def test_shaft_measurements(self):
        print("\n=== Testing Shaft Measurements ===")
        ts = int(time.time())
        pid = f"SHAFT_TEST_{ts}"
        data = {"product_id": pid, "roll_number": f"TEST_ROLL_{ts}", "shaft_height": 25.5, "shaft_radius": 12.3}
        r = self.make_request("POST", "/shaft_measurement", data=data)
        if r["success"] and r["response"].get("status") == "shaft measurement added":
            self.log_test("/shaft_measurement", "Valid shaft", "PASS")
        else:
            self.log_test("/shaft_measurement", "Valid shaft", "FAIL", f"Unexpected: {r}")
        r = self.make_request("POST", "/shaft_measurement", data=data, expected_status=409)
        if r["status_code"] == 409:
            self.log_test("/shaft_measurement", "Duplicate pid", "PASS")
        else:
            self.log_test("/shaft_measurement", "Duplicate pid", "FAIL", f"Got: {r['status_code']}")
        bad = {"product_id": f"SHAFT_BAD_{ts}", "roll_number": f"TEST_BAD_{ts}"}
        r = self.make_request("POST", "/shaft_measurement", data=bad, expected_status=400)
        if r["status_code"] == 400:
            self.log_test("/shaft_measurement", "Missing fields", "PASS")
        else:
            self.log_test("/shaft_measurement", "Missing fields", "FAIL", f"Got: {r['status_code']}")

    def test_housing_measurements(self):
        print("\n=== Testing Housing Measurements ===")
        ts = int(time.time())
        for i, ht in enumerate(["housing", "oval", "sqaure", "angular"]):
            pid = f"HOUSING_TEST_{ts}_{i}"
            data = {"product_id": pid, "roll_number": f"TEST_ROLL_{ts}_{i}", "housing_type": ht,
                    "housing_height": 25.5 + i, "housing_radius": 12.3 + i, "housing_depth": 8.7 + i}
            r = self.make_request("POST", "/housing_measurement", data=data)
            if r["success"] and r["response"].get("status") == "housing measurement added":
                self.log_test("/housing_measurement", f"Valid {ht}", "PASS")
                if i == 0:
                    self.last_housing_id = pid
            else:
                self.log_test("/housing_measurement", f"Valid {ht}", "FAIL", f"Unexpected: {r}")
        dup = {"product_id": f"HOUSING_TEST_{ts}_0", "roll_number": f"TEST_DUP_{ts}", "housing_type": "oval",
               "housing_height": 30.0, "housing_radius": 15.0, "housing_depth": 10.0}
        r = self.make_request("POST", "/housing_measurement", data=dup, expected_status=409)
        if r["status_code"] == 409:
            self.log_test("/housing_measurement", "Duplicate pid", "PASS")
        else:
            self.log_test("/housing_measurement", "Duplicate pid", "FAIL", f"Got: {r['status_code']}")
        bad_type = {"product_id": f"HOUSING_TEST_BAD_{ts}", "roll_number": f"TEST_BAD_{ts}", "housing_type": "bad",
                    "housing_height": 25.0, "housing_radius": 12.0, "housing_depth": 8.0}
        r = self.make_request("POST", "/housing_measurement", data=bad_type, expected_status=400)
        if r["status_code"] == 400:
            self.log_test("/housing_measurement", "Invalid type", "PASS")
        else:
            self.log_test("/housing_measurement", "Invalid type", "FAIL", f"Got: {r['status_code']}")
        missing = {"product_id": f"HOUSING_TEST_MISS_{ts}", "roll_number": f"TEST_MISS_{ts}",
                   "housing_height": 25.0, "housing_radius": 12.0, "housing_depth": 8.0}
        r = self.make_request("POST", "/housing_measurement", data=missing, expected_status=400)
        if r["status_code"] == 400:
            self.log_test("/housing_measurement", "Missing housing_type", "PASS")
        else:
            self.log_test("/housing_measurement", "Missing housing_type", "FAIL", f"Got: {r['status_code']}")

    def test_measured_units(self):
        print("\n=== Testing Measured Units ===")
        r = self.make_request("GET", "/measured_units/TEST_ROLL_001")
        if r["success"] and isinstance(r["response"], dict):
            data = r["response"]
            if "shaft_measurements" in data and "housing_measurements" in data:
                self.log_test("/measured_units/{roll_number}", "Existing roll", "PASS")
            else:
                self.log_test("/measured_units/{roll_number}", "Existing roll", "FAIL", f"Missing keys: {data}")
        else:
            self.log_test("/measured_units/{roll_number}", "Existing roll", "FAIL", f"Unexpected: {r}")
        r = self.make_request("GET", "/measured_units/NONEXISTENT_ROLL")
        if r["success"]:
            d = r["response"]
            if d.get("shaft_measurements") == [] and d.get("housing_measurements") == []:
                self.log_test("/measured_units/{roll_number}", "Non-existent roll", "PASS")
            else:
                self.log_test("/measured_units/{roll_number}", "Non-existent roll", "FAIL", f"Unexpected: {d}")
        else:
            self.log_test("/measured_units/{roll_number}", "Non-existent roll", "FAIL", f"Unexpected: {r}")

    def test_schema_endpoints(self):
        print("\n=== Testing Schema Endpoints ===")
        r = self.make_request("GET", "/db/schema/tables")
        if r["success"] and isinstance(r["response"].get("tables"), list):
            tables = set(r["response"]["tables"])
            needed = {"measured_shafts", "measured_housings", "user_entry"}
            if needed.issubset(tables):
                self.log_test("/db/schema/tables", "List tables", "PASS")
            else:
                self.log_test("/db/schema/tables", "List tables", "FAIL", f"Missing: {needed - tables}")
        else:
            self.log_test("/db/schema/tables", "List tables", "FAIL", f"Unexpected: {r}")
        r = self.make_request("GET", "/db/schema/tables/measured_housings")
        if r["success"] and r["response"].get("table") == "measured_housings" and any(c.get("name") == "product_id" for c in r["response"].get("columns", [])):
            self.log_test("/db/schema/tables/{table}", "Describe measured_housings", "PASS")
        else:
            self.log_test("/db/schema/tables/{table}", "Describe measured_housings", "FAIL", f"Unexpected: {r}")

    def test_generic_queries(self):
        print("\n=== Testing Generic Query Endpoints ===")
        shaft_pid = f"GENERIC_SHAFT_{int(time.time())}"
        shaft_data = {"product_id": shaft_pid, "roll_number": f"GENERIC_ROLL_{int(time.time())}", "shaft_height": 11.11, "shaft_radius": 22.22}
        ins = self.make_request("POST", "/shaft_measurement", data=shaft_data)
        if ins["success"]:
            self.log_test("/shaft_measurement", "Insert shaft generic", "PASS")
            self.last_shaft_id = shaft_pid
        else:
            self.log_test("/shaft_measurement", "Insert shaft generic", "FAIL", f"Unexpected: {ins}")
            return
        sel_body = {"table": "measured_shafts", "filters": {"product_id": shaft_pid}, "limit": 5}
        sel = self.make_request("POST", "/db/query/select", data=sel_body)
        if sel["success"] and sel["response"].get("count") == 1:
            self.log_test("/db/query/select", "Select shaft", "PASS")
        else:
            self.log_test("/db/query/select", "Select shaft", "FAIL", f"Unexpected: {sel}")
        upd_body = {"table": "measured_shafts", "set": {"shaft_height": 99.99}, "filters": {"product_id": shaft_pid}}
        upd = self.make_request("POST", "/db/query/update", data=upd_body)
        if upd["success"] and upd["response"].get("updated") == 1:
            self.log_test("/db/query/update", "Update shaft", "PASS")
        else:
            self.log_test("/db/query/update", "Update shaft", "FAIL", f"Unexpected: {upd}")
        sel2 = self.make_request("POST", "/db/query/select", data=sel_body)
        if sel2["success"] and sel2["response"].get("data") and abs(sel2["response"]["data"][0].get("shaft_height", 0) - 99.99) < 1e-6:
            self.log_test("/db/query/select", "Confirm shaft update", "PASS")
        else:
            self.log_test("/db/query/select", "Confirm shaft update", "FAIL", f"Unexpected: {sel2}")
        housing_pid = f"GENERIC_HOUSING_{int(time.time())}"
        housing_data = {"product_id": housing_pid, "roll_number": f"GENERIC_ROLL_{int(time.time())}", "housing_type": "housing", "housing_height": 5.5, "housing_radius": 3.3, "housing_depth": 1.1}
        h_ins = self.make_request("POST", "/housing_measurement", data=housing_data)
        if h_ins["success"]:
            self.log_test("/housing_measurement", "Insert housing generic", "PASS")
            self.last_housing_id = housing_pid
        else:
            self.log_test("/housing_measurement", "Insert housing generic", "FAIL", f"Unexpected: {h_ins}")
            return
        h_sel_body = {"table": "measured_housings", "filters": {"product_id": housing_pid}}
        h_sel = self.make_request("POST", "/db/query/select", data=h_sel_body)
        if h_sel["success"] and h_sel["response"].get("count") == 1:
            self.log_test("/db/query/select", "Select housing", "PASS")
        else:
            self.log_test("/db/query/select", "Select housing", "FAIL", f"Unexpected: {h_sel}")
        h_up_body = {"table": "measured_housings", "set": {"housing_radius": 7.7}, "filters": {"product_id": housing_pid}}
        h_up = self.make_request("POST", "/db/query/update", data=h_up_body)
        if h_up["success"] and h_up["response"].get("updated") == 1:
            self.log_test("/db/query/update", "Update housing", "PASS")
        else:
            self.log_test("/db/query/update", "Update housing", "FAIL", f"Unexpected: {h_up}")
        h_sel2 = self.make_request("POST", "/db/query/select", data=h_sel_body)
        if h_sel2["success"] and h_sel2["response"].get("data") and abs(h_sel2["response"]["data"][0].get("housing_radius", 0) - 7.7) < 1e-6:
            self.log_test("/db/query/select", "Confirm housing update", "PASS")
        else:
            self.log_test("/db/query/select", "Confirm housing update", "FAIL", f"Unexpected: {h_sel2}")

    def test_video_streaming(self):
        print("\n=== Testing Video Streaming ===")
        r = self.make_request("HEAD", "/video/shaft/shaft_height.mkv")
        if r["status_code"] in [200, 404]:
            self.log_test("/video/{category}/{filename}", "HEAD request", "PASS")
        else:
            self.log_test("/video/{category}/{filename}", "HEAD request", "FAIL", f"Status: {r['status_code']}")
        r = self.make_request("GET", "/video/invalid_category/test.mkv", expected_status=404)
        if r["status_code"] == 404:
            self.log_test("/video/{category}/{filename}", "Invalid category", "PASS")
        else:
            self.log_test("/video/{category}/{filename}", "Invalid category", "FAIL", f"Got: {r['status_code']}")

    # ----------------------- orchestrator -----------------------
    def run_all_tests(self):
        print("🚀 Starting API Endpoint Tests...")
        print(f"Base URL: {self.base_url}")
        try:
            resp = requests.get(f"{self.base_url}/", timeout=5)
            if resp.status_code not in [200, 404]:
                print(f"❌ Server not responding. Status: {resp.status_code}")
                return
            print("✅ Server is running!")
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to server at {self.base_url}")
            return
        # Execute tests
        self.test_root_endpoint()
        self.test_housing_types()
        self.test_video_endpoints()
        self.test_product_exists()
        self.test_shaft_measurements()
        self.test_housing_measurements()
        self.test_measured_units()
        self.test_schema_endpoints()
        self.test_generic_queries()
        self.test_video_streaming()
        self.print_summary()

    def print_summary(self):
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.total_tests}")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        rate = (self.passed_tests / self.total_tests * 100) if self.total_tests else 0
        print(f"Success Rate: {rate:.1f}%")
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for r in self.test_results:
                if r["status"] == "FAIL":
                    print(f"  - {r['endpoint']} - {r['test_case']}: {r['details']}")
        self.save_results_to_file()

    def save_results_to_file(self):
        filename = f"api_test_results_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": self.total_tests,
                    "passed_tests": self.passed_tests,
                    "failed_tests": self.failed_tests,
                    "success_rate": f"{(self.passed_tests / self.total_tests * 100) if self.total_tests else 0:.1f}%"
                },
                "detailed_results": self.test_results
            }, f, indent=2)
        print(f"\n📄 Detailed results saved to: {filename}")

if __name__ == "__main__":
    # You can customize the base URL here
    tester = APITester("http://127.0.0.1:5000")
    tester.run_all_tests()