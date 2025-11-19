"""Test runner for all test suites."""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def run_all_tests():
    """Run all test suites."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Get the tests directory path
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    
    # Add unit tests
    unit_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'unit'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(unit_tests)
    
    # Add integration tests
    integration_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'integration'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(integration_tests)
    
    # Add validation tests
    validation_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'validation'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(validation_tests)
    
    # Add performance tests
    performance_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'performance'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(performance_tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

