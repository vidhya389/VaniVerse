"""
Integration test runner for VaniVerse

Runs comprehensive integration tests and generates a report.
"""

import subprocess
import sys
import os
import json
from datetime import datetime


def run_tests(test_type="all", verbose=False):
    """
    Run integration tests
    
    Args:
        test_type: Type of tests to run ("all", "guru_cycle", "performance", "languages", "errors")
        verbose: Whether to show verbose output
    """
    print("=" * 80)
    print("VaniVerse Integration Test Runner")
    print("=" * 80)
    print(f"Test Type: {test_type}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    # Build pytest command
    cmd = ["pytest", "-v", "-m", "integration"]
    
    if verbose:
        cmd.append("-vv")
    
    # Add specific test markers based on test_type
    if test_type == "guru_cycle":
        cmd.append("tests/test_integration_guru_cycle.py::TestGuruCycleIntegration")
    elif test_type == "performance":
        cmd.append("tests/test_integration_performance.py")
    elif test_type == "languages":
        cmd.append("tests/test_integration_guru_cycle.py::TestMultiLanguageIntegration")
    elif test_type == "errors":
        cmd.append("tests/test_integration_guru_cycle.py::TestErrorScenarioIntegration")
    elif test_type == "all":
        cmd.extend([
            "tests/test_integration_guru_cycle.py",
            "tests/test_integration_performance.py"
        ])
    else:
        print(f"Unknown test type: {test_type}")
        return False
    
    # Add JSON report output
    report_file = f"integration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    cmd.extend(["--json-report", f"--json-report-file={report_file}"])
    
    # Run tests
    print(f"Running command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        print()
        print("=" * 80)
        if result.returncode == 0:
            print("✓ All integration tests passed!")
        else:
            print("✗ Some integration tests failed")
        print("=" * 80)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"✗ Error running tests: {e}")
        return False


def run_language_tests():
    """Run tests for all 8 supported languages"""
    print("=" * 80)
    print("Testing All 8 Supported Languages")
    print("=" * 80)
    print()
    
    languages = [
        ('hi-IN', 'Hindi'),
        ('ta-IN', 'Tamil'),
        ('te-IN', 'Telugu'),
        ('kn-IN', 'Kannada'),
        ('mr-IN', 'Marathi'),
        ('bn-IN', 'Bengali'),
        ('gu-IN', 'Gujarati'),
        ('pa-IN', 'Punjabi')
    ]
    
    results = {}
    
    for lang_code, lang_name in languages:
        print(f"Testing {lang_name} ({lang_code})...")
        
        cmd = [
            "pytest",
            "-v",
            "tests/test_integration_guru_cycle.py::TestMultiLanguageIntegration::test_language_support_end_to_end",
            "-k", lang_code
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            results[lang_name] = result.returncode == 0
            
            if result.returncode == 0:
                print(f"  ✓ {lang_name} passed")
            else:
                print(f"  ✗ {lang_name} failed")
        except Exception as e:
            print(f"  ✗ {lang_name} error: {e}")
            results[lang_name] = False
    
    print()
    print("=" * 80)
    print("Language Test Summary")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for lang_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"{status}: {lang_name}")
    
    print()
    print(f"Total: {passed}/{total} languages passed")
    print("=" * 80)
    
    return passed == total


def run_performance_benchmarks():
    """Run performance benchmarks and report results"""
    print("=" * 80)
    print("Performance Benchmarks")
    print("=" * 80)
    print()
    
    cmd = [
        "pytest",
        "-v",
        "-m", "performance",
        "tests/test_integration_performance.py",
        "-s"  # Show print statements for timing info
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        print()
        print("=" * 80)
        if result.returncode == 0:
            print("✓ All performance benchmarks passed")
        else:
            print("✗ Some performance benchmarks failed")
        print("=" * 80)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"✗ Error running benchmarks: {e}")
        return False


def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run VaniVerse integration tests")
    parser.add_argument(
        "--type",
        choices=["all", "guru_cycle", "performance", "languages", "errors", "benchmarks"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose output"
    )
    
    args = parser.parse_args()
    
    # Check if pytest is installed
    try:
        subprocess.run(["pytest", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ pytest is not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Run tests based on type
    if args.type == "languages":
        success = run_language_tests()
    elif args.type == "benchmarks":
        success = run_performance_benchmarks()
    else:
        success = run_tests(args.type, args.verbose)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
