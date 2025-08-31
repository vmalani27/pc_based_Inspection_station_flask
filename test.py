import requests
import json
import os
import time
from typing import Dict, Any, List
import traceback

class APITester:
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

    def log_test(self, endpoint: str, test_case: str, status: str, details: str = ""):
        """Log test results"""
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

    def make_request(self, method: str, endpoint: str, data: Dict = None, files: Dict = None, 
                    params: Dict = None, expected_status: int = 200) -> Dict:
        """Make HTTP request with error handling"""
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
            return {
                "status_code": None,
                "response": str(e),
                "success": False
            }

    def test_root_endpoint(self):
        """Test root endpoint"""
        print("\n=== Testing Root Endpoint ===")
        
        # Test root endpoint
        result = self.make_request("GET", "/")
        if result["success"]:
            self.log_test("/", "Root endpoint check", "PASS")
        else:
            self.log_test("/", "Root endpoint check", "FAIL", f"Status: {result['status_code']}")

    def test_housing_types(self):
        """Test /housing_types endpoint"""
        print("\n=== Testing Housing Types ===")
        
        # Success case
        result = self.make_request("GET", "/housing_types")
        if result["success"] and "housing_types" in result["response"]:
            expected_types = ["oval", "sqaure", "angular"]
            actual_types = result["response"]["housing_types"]
            if all(t in actual_types for t in expected_types):
                self.log_test("/housing_types", "Get housing types", "PASS")
            else:
                self.log_test("/housing_types", "Get housing types", "FAIL", 
                            f"Missing types. Expected: {expected_types}, Got: {actual_types}")
        else:
            self.log_test("/housing_types", "Get housing types", "FAIL", f"Unexpected response: {result}")

    def test_video_endpoints(self):
        """Test video-related endpoints"""
        print("\n=== Testing Video Endpoints ===")
        
        # Test video list for valid categories
        categories = ["housing", "shaft", "oval_housing", "sqaure_housing", "angular_housing"]
        
        for category in categories:
            result = self.make_request("GET", f"/video/list/{category}")
            if result["success"] and isinstance(result["response"], list):
                self.log_test(f"/video/list/{category}", f"List videos for {category}", "PASS")
            else:
                self.log_test(f"/video/list/{category}", f"List videos for {category}", "FAIL", 
                            f"Expected list, got: {result}")
        
        # Test invalid category
        result = self.make_request("GET", "/video/list/invalid_category", expected_status=404)
        if result["status_code"] == 404:
            self.log_test("/video/list/invalid", "Invalid category", "PASS")
        else:
            self.log_test("/video/list/invalid", "Invalid category", "FAIL", 
                        f"Expected 404, got: {result['status_code']}")
        
        # Test housing types video endpoints
        housing_types = ["oval", "sqaure", "angular"]
        for housing_type in housing_types:
            result = self.make_request("GET", f"/video/housing_types/{housing_type}")
            if result["success"] and isinstance(result["response"], list):
                self.log_test(f"/video/housing_types/{housing_type}", f"Housing type videos", "PASS")
            else:
                self.log_test(f"/video/housing_types/{housing_type}", f"Housing type videos", "FAIL", 
                            f"Expected list, got: {result}")
        
        # Test invalid housing type
        result = self.make_request("GET", "/video/housing_types/invalid", expected_status=400)
        if result["status_code"] == 400:
            self.log_test("/video/housing_types/invalid", "Invalid housing type", "PASS")
        else:
            self.log_test("/video/housing_types/invalid", "Invalid housing type", "FAIL", 
                        f"Expected 400, got: {result['status_code']}")

    def test_product_exists(self):
        """Test /product_exists endpoint"""
        print("\n=== Testing Product Exists ===")
        
        # Test with valid measurement types
        measurement_types = ["shaft", "housing"]
        for measurement_type in measurement_types:
            # Test with non-existent product ID
            result = self.make_request("GET", "/product_exists", 
                                     params={"product_id": "NONEXISTENT123", "measurement_type": measurement_type})
            if (result["success"] and 
                result["response"].get("measurement_type") == measurement_type and
                result["response"].get("exists") == False):
                self.log_test("/product_exists", f"Non-existent {measurement_type} product", "PASS")
            else:
                self.log_test("/product_exists", f"Non-existent {measurement_type} product", "FAIL", 
                            f"Unexpected response: {result}")
        
        # Test missing parameters
        result = self.make_request("GET", "/product_exists", expected_status=422)
        if result["status_code"] == 422:
            self.log_test("/product_exists", "Missing parameters", "PASS")
        else:
            self.log_test("/product_exists", "Missing parameters", "FAIL", 
                        f"Expected 422, got: {result['status_code']}")
        
        # Test invalid measurement type
        result = self.make_request("GET", "/product_exists", 
                                 params={"product_id": "TEST123", "measurement_type": "invalid"}, 
                                 expected_status=400)
        if result["status_code"] == 400:
            self.log_test("/product_exists", "Invalid measurement type", "PASS")
        else:
            self.log_test("/product_exists", "Invalid measurement type", "FAIL", 
                        f"Expected 400, got: {result['status_code']}")

    def test_shaft_measurements(self):
        """Test shaft measurement endpoints"""
        print("\n=== Testing Shaft Measurements ===")
        
        # Generate unique product ID with timestamp
        timestamp = int(time.time())
        unique_product_id = f"SHAFT_TEST_{timestamp}"
        
        # Test valid shaft measurement
        valid_shaft_data = {
            "product_id": unique_product_id,
            "roll_number": f"TEST_ROLL_{timestamp}",
            "shaft_height": 25.5,
            "shaft_radius": 12.3
        }
        
        result = self.make_request("POST", "/shaft_measurement", data=valid_shaft_data)
        if result["success"] and result["response"].get("status") == "shaft measurement added":
            self.log_test("/shaft_measurement", "Valid shaft measurement", "PASS")
        else:
            self.log_test("/shaft_measurement", "Valid shaft measurement", "FAIL", 
                        f"Unexpected response: {result}")
        
        # Test duplicate product ID (use same ID as above)
        result = self.make_request("POST", "/shaft_measurement", data=valid_shaft_data, expected_status=409)
        if result["status_code"] == 409:
            self.log_test("/shaft_measurement", "Duplicate product ID", "PASS")
        else:
            self.log_test("/shaft_measurement", "Duplicate product ID", "FAIL", 
                        f"Expected 409, got: {result['status_code']}")
        
        # Test missing fields
        invalid_shaft_data = {
            "product_id": f"SHAFT_TEST_INVALID_{timestamp}",
            "roll_number": f"TEST_ROLL_INVALID_{timestamp}"
            # Missing shaft_height and shaft_radius
        }
        
        result = self.make_request("POST", "/shaft_measurement", data=invalid_shaft_data, expected_status=400)
        if result["status_code"] == 400:
            self.log_test("/shaft_measurement", "Missing required fields", "PASS")
        else:
            self.log_test("/shaft_measurement", "Missing required fields", "FAIL", 
                        f"Expected 400, got: {result['status_code']}")

    def test_housing_measurements(self):
        """Test housing measurement endpoints"""
        print("\n=== Testing Housing Measurements ===")
        
        timestamp = int(time.time())
        housing_types = ["housing", "oval", "sqaure", "angular"]
        
        # Test valid housing measurements for each type
        for i, housing_type in enumerate(housing_types):
            unique_product_id = f"HOUSING_TEST_{timestamp}_{i}"
            valid_housing_data = {
                "product_id": unique_product_id,
                "roll_number": f"TEST_ROLL_{timestamp}_{i}",
                "housing_type": housing_type,
                "housing_height": 25.5 + i,
                "housing_radius": 12.3 + i,
                "housing_depth": 8.7 + i
            }
            
            result = self.make_request("POST", "/housing_measurement", data=valid_housing_data)
            if result["success"] and result["response"].get("status") == "housing measurement added":
                self.log_test("/housing_measurement", f"Valid {housing_type} measurement", "PASS")
            else:
                self.log_test("/housing_measurement", f"Valid {housing_type} measurement", "FAIL", 
                            f"Unexpected response: {result}")
        
        # Test duplicate product ID (reuse first product ID)
        duplicate_data = {
            "product_id": f"HOUSING_TEST_{timestamp}_0",  # Same as first test
            "roll_number": f"TEST_ROLL_DUPLICATE_{timestamp}",
            "housing_type": "oval",
            "housing_height": 30.0,
            "housing_radius": 15.0,
            "housing_depth": 10.0
        }
        
        result = self.make_request("POST", "/housing_measurement", data=duplicate_data, expected_status=409)
        if result["status_code"] == 409:
            self.log_test("/housing_measurement", "Duplicate product ID", "PASS")
        else:
            self.log_test("/housing_measurement", "Duplicate product ID", "FAIL", 
                        f"Expected 409, got: {result['status_code']}")
        
        # Test invalid housing type
        invalid_type_data = {
            "product_id": f"HOUSING_TEST_INVALID_{timestamp}",
            "roll_number": f"TEST_ROLL_INVALID_{timestamp}",
            "housing_type": "invalid_type",
            "housing_height": 25.0,
            "housing_radius": 12.0,
            "housing_depth": 8.0
        }
        
        result = self.make_request("POST", "/housing_measurement", data=invalid_type_data, expected_status=400)
        if result["status_code"] == 400:
            self.log_test("/housing_measurement", "Invalid housing type", "PASS")
        else:
            self.log_test("/housing_measurement", "Invalid housing type", "FAIL", 
                        f"Expected 400, got: {result['status_code']}")
        
        # Test missing housing_type field
        missing_type_data = {
            "product_id": f"HOUSING_TEST_MISSING_{timestamp}",
            "roll_number": f"TEST_ROLL_MISSING_{timestamp}",
            "housing_height": 25.0,
            "housing_radius": 12.0,
            "housing_depth": 8.0
        }
        
        result = self.make_request("POST", "/housing_measurement", data=missing_type_data, expected_status=400)
        if result["status_code"] == 400:
            self.log_test("/housing_measurement", "Missing housing_type field", "PASS")
        else:
            self.log_test("/housing_measurement", "Missing housing_type field", "FAIL", 
                        f"Expected 400, got: {result['status_code']}")

    def test_measured_units(self):
        """Test measured units retrieval"""
        print("\n=== Testing Measured Units ===")
        
        # Test with existing roll number
        result = self.make_request("GET", "/measured_units/TEST_ROLL_001")
        if result["success"] and isinstance(result["response"], dict):
            response_data = result["response"]
            if ("shaft_measurements" in response_data and 
                "housing_measurements" in response_data):
                self.log_test("/measured_units/{roll_number}", "Get existing measurements", "PASS")
            else:
                self.log_test("/measured_units/{roll_number}", "Get existing measurements", "FAIL", 
                            f"Missing measurement types in response: {response_data}")
        else:
            self.log_test("/measured_units/{roll_number}", "Get existing measurements", "FAIL", 
                        f"Unexpected response: {result}")
        
        # Test with non-existent roll number
        result = self.make_request("GET", "/measured_units/NONEXISTENT_ROLL")
        if result["success"]:
            response_data = result["response"]
            if (response_data.get("shaft_measurements") == [] and 
                response_data.get("housing_measurements") == []):
                self.log_test("/measured_units/{roll_number}", "Non-existent roll number", "PASS")
            else:
                self.log_test("/measured_units/{roll_number}", "Non-existent roll number", "FAIL", 
                            f"Expected empty arrays, got: {response_data}")
        else:
            self.log_test("/measured_units/{roll_number}", "Non-existent roll number", "FAIL", 
                        f"Unexpected response: {result}")

    def test_clear_csv_endpoints(self):
        """Test CSV clearing endpoints"""
        print("\n=== Testing Clear CSV Endpoints ===")
        
        # Test clear shaft CSV
        result = self.make_request("POST", "/clear_shaft_csv")
        if result["success"] and result["response"].get("status") == "shaft CSV cleared":
            self.log_test("/clear_shaft_csv", "Clear shaft CSV", "PASS")
        else:
            self.log_test("/clear_shaft_csv", "Clear shaft CSV", "FAIL", 
                        f"Unexpected response: {result}")
        
        # Test clear housing CSV
        result = self.make_request("POST", "/clear_housing_csv")
        if result["success"] and result["response"].get("status") == "housing CSV cleared":
            self.log_test("/clear_housing_csv", "Clear housing CSV", "PASS")
        else:
            self.log_test("/clear_housing_csv", "Clear housing CSV", "FAIL", 
                        f"Unexpected response: {result}")
        
        # Test clear user entry CSV
        result = self.make_request("POST", "/clear_user_entry_csv")
        if result["success"] and result["response"].get("status") == "user entry CSV cleared":
            self.log_test("/clear_user_entry_csv", "Clear user entry CSV", "PASS")
        else:
            self.log_test("/clear_user_entry_csv", "Clear user entry CSV", "FAIL", 
                        f"Unexpected response: {result}")

    def test_video_streaming(self):
        """Test video file streaming"""
        print("\n=== Testing Video Streaming ===")
        
        # Test HEAD request for video existence
        result = self.make_request("HEAD", "/video/shaft/shaft_height.mkv")
        if result["status_code"] in [200, 404]:  # Either file exists or doesn't
            self.log_test("/video/{category}/{filename}", "HEAD request", "PASS")
        else:
            self.log_test("/video/{category}/{filename}", "HEAD request", "FAIL", 
                        f"Unexpected status: {result['status_code']}")
        
        # Test invalid category
        result = self.make_request("GET", "/video/invalid_category/test.mkv", expected_status=404)
        if result["status_code"] == 404:
            self.log_test("/video/{category}/{filename}", "Invalid category", "PASS")
        else:
            self.log_test("/video/{category}/{filename}", "Invalid category", "FAIL", 
                        f"Expected 404, got: {result['status_code']}")

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting API Endpoint Tests...")
        print(f"Base URL: {self.base_url}")
        
        # Check if server is running by testing root endpoint
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code not in [200, 404]:  # Accept both as server running
                print(f"❌ Server not responding correctly. Status: {response.status_code}")
                return
            print("✅ Server is running!")
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to server at {self.base_url}")
            print("Please make sure the backend is running.")
            return
        
        # Run all test suites
        self.test_root_endpoint()
        self.test_housing_types()
        self.test_video_endpoints()
        self.test_product_exists()
        self.test_shaft_measurements()
        self.test_housing_measurements()
        self.test_measured_units()
        self.test_clear_csv_endpoints()
        self.test_video_streaming()
        
        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.total_tests}")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")
        
        if self.failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"  - {result['endpoint']} - {result['test_case']}: {result['details']}")
        
        # Save detailed results to file
        self.save_results_to_file()

    def save_results_to_file(self):
        """Save test results to a JSON file"""
        filename = f"api_test_results_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": self.total_tests,
                    "passed_tests": self.passed_tests,
                    "failed_tests": self.failed_tests,
                    "success_rate": f"{(self.passed_tests/self.total_tests*100):.1f}%"
                },
                "detailed_results": self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {filename}")

if __name__ == "__main__":
    # You can customize the base URL here
    tester = APITester("http://127.0.0.1:5000")
    tester.run_all_tests()