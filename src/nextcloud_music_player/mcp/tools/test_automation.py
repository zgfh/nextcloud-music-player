"""
Test automation tool.

This tool provides automated testing functionality.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class TestAutomationTool(BaseTool):
    """Tool for automating testing tasks."""
    
    @property
    def name(self) -> str:
        return "test_automation"
    
    @property
    def description(self) -> str:
        return "Automate testing tasks like running unit tests, integration tests, and generating coverage reports"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["run_tests", "run_coverage", "create_test", "run_specific", "test_performance"],
                    "description": "The testing action to perform"
                },
                "test_type": {
                    "type": "string",
                    "enum": ["unit", "integration", "performance", "all"],
                    "description": "Type of tests to run"
                },
                "test_file": {
                    "type": "string",
                    "description": "Specific test file to run"
                },
                "test_name": {
                    "type": "string",
                    "description": "Name for new test"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Verbose output"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the testing action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        test_type = arguments.get("test_type", "all")
        test_file = arguments.get("test_file")
        test_name = arguments.get("test_name")
        verbose = arguments.get("verbose", False)
        
        try:
            if action == "run_tests":
                return await self._run_tests(test_type, verbose)
            elif action == "run_coverage":
                return await self._run_coverage()
            elif action == "create_test":
                return await self._create_test(test_name)
            elif action == "run_specific":
                return await self._run_specific_test(test_file)
            elif action == "test_performance":
                return await self._test_performance()
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in test automation: {e}")
            return {"error": str(e)}
    
    async def _run_tests(self, test_type: str, verbose: bool) -> Dict[str, Any]:
        """Run tests."""
        if test_type == "unit":
            command = "python -m unittest discover tests/ -v" if verbose else "python -m unittest discover tests/"
        elif test_type == "integration":
            command = "python -m tests.test_basic"
        else:
            # Run all tests
            command = "python -m tests.test_basic && python -m tests.test_minimal"
        
        self.logger.info(f"Running {test_type} tests")
        result = self.run_command(command)
        
        # Parse test results
        test_results = self._parse_test_output(result["stdout"], result["stderr"])
        
        return {
            "success": result["success"],
            "message": f"Tests completed ({test_type})",
            "test_type": test_type,
            "output": result["stdout"],
            "error": result["stderr"] if not result["success"] else None,
            "test_results": test_results
        }
    
    async def _run_coverage(self) -> Dict[str, Any]:
        """Run tests with coverage analysis."""
        # First try to install coverage if not available
        install_result = self.run_command("pip install coverage")
        
        commands = [
            "coverage run -m unittest discover tests/",
            "coverage report",
            "coverage html"
        ]
        
        results = []
        for command in commands:
            result = self.run_command(command)
            results.append({
                "command": command,
                "success": result["success"],
                "output": result["stdout"],
                "error": result["stderr"]
            })
        
        # Check if HTML coverage report was generated
        coverage_html = self.project_root / "htmlcov"
        html_report_available = coverage_html.exists()
        
        return {
            "success": all(r["success"] for r in results),
            "message": "Coverage analysis completed",
            "results": results,
            "html_report_available": html_report_available,
            "html_report_path": str(coverage_html) if html_report_available else None
        }
    
    async def _create_test(self, test_name: str) -> Dict[str, Any]:
        """Create a new test file."""
        if not test_name:
            return {"error": "Test name is required"}
        
        test_file_name = f"test_{test_name.lower()}.py"
        class_name = f"Test{''.join(word.capitalize() for word in test_name.split('_'))}"
        
        test_content = f'''"""
Test suite for {test_name} functionality.
"""

import unittest
import sys
import os
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from nextcloud_music_player.app import NextCloudMusicPlayer


class {class_name}(unittest.TestCase):
    """Test case for {test_name} functionality."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = None
        # Add setup code here
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        if self.app:
            # Add cleanup code here
            pass
    
    def test_{test_name}_basic(self):
        """Test basic {test_name} functionality."""
        # Add test implementation here
        self.assertTrue(True, "Basic test should pass")
    
    def test_{test_name}_edge_cases(self):
        """Test {test_name} edge cases."""
        # Add edge case tests here
        self.assertTrue(True, "Edge case test should pass")
    
    def test_{test_name}_error_handling(self):
        """Test {test_name} error handling."""
        # Add error handling tests here
        self.assertTrue(True, "Error handling test should pass")


if __name__ == '__main__':
    unittest.main()
'''
        
        test_path = self.project_root / "tests" / test_file_name
        
        if test_path.exists():
            return {"error": f"Test file already exists: {test_path}"}
        
        if not self.write_file(test_path, test_content):
            return {"error": f"Failed to create test file: {test_path}"}
        
        return {
            "success": True,
            "message": f"Created test: {class_name}",
            "test_file": str(test_path),
            "class_name": class_name
        }
    
    async def _run_specific_test(self, test_file: str) -> Dict[str, Any]:
        """Run a specific test file."""
        if not test_file:
            return {"error": "Test file is required"}
        
        # Convert to module path
        if test_file.endswith(".py"):
            test_file = test_file[:-3]
        
        if not test_file.startswith("tests."):
            test_file = f"tests.{test_file}"
        
        command = f"python -m {test_file}"
        
        self.logger.info(f"Running specific test: {test_file}")
        result = self.run_command(command)
        
        return {
            "success": result["success"],
            "message": f"Specific test completed: {test_file}",
            "test_file": test_file,
            "output": result["stdout"],
            "error": result["stderr"] if not result["success"] else None
        }
    
    async def _test_performance(self) -> Dict[str, Any]:
        """Run performance tests."""
        # Create a simple performance test
        perf_test_content = '''
import time
import unittest
import sys
import os
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class PerformanceTest(unittest.TestCase):
    """Performance test suite."""
    
    def test_app_startup_time(self):
        """Test application startup time."""
        start_time = time.time()
        
        try:
            from nextcloud_music_player.app import NextCloudMusicPlayer
            # Simulate app initialization without GUI
            app_config = {}
            # Test basic imports and setup
            self.assertTrue(True)
            
        except Exception as e:
            self.fail(f"App startup failed: {e}")
        
        startup_time = time.time() - start_time
        self.assertLess(startup_time, 5.0, f"Startup time too slow: {startup_time:.2f}s")
        print(f"App startup time: {startup_time:.2f}s")
    
    def test_config_loading_time(self):
        """Test configuration loading performance."""
        start_time = time.time()
        
        try:
            from nextcloud_music_player.config_manager import ConfigManager
            config = ConfigManager()
            # Test config operations
            self.assertTrue(True)
            
        except Exception as e:
            self.fail(f"Config loading failed: {e}")
        
        load_time = time.time() - start_time
        self.assertLess(load_time, 1.0, f"Config loading too slow: {load_time:.2f}s")
        print(f"Config loading time: {load_time:.2f}s")


if __name__ == '__main__':
    unittest.main()
'''
        
        perf_test_path = self.project_root / "tests" / "test_performance.py"
        self.write_file(perf_test_path, perf_test_content)
        
        # Run performance test
        command = "python -m tests.test_performance"
        result = self.run_command(command)
        
        return {
            "success": result["success"],
            "message": "Performance tests completed",
            "output": result["stdout"],
            "error": result["stderr"] if not result["success"] else None,
            "performance_test_created": str(perf_test_path)
        }
    
    def _parse_test_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """Parse test output to extract results."""
        lines = (stdout + stderr).split('\\n')
        
        tests_run = 0
        failures = 0
        errors = 0
        skipped = 0
        
        for line in lines:
            if "Ran" in line and "test" in line:
                # Extract number of tests run
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        tests_run = int(part)
                        break
            
            if "failures=" in line:
                # Extract failures count
                import re
                match = re.search(r'failures=(\d+)', line)
                if match:
                    failures = int(match.group(1))
            
            if "errors=" in line:
                # Extract errors count
                import re
                match = re.search(r'errors=(\d+)', line)
                if match:
                    errors = int(match.group(1))
        
        return {
            "tests_run": tests_run,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "success_rate": (tests_run - failures - errors) / tests_run if tests_run > 0 else 0
        }