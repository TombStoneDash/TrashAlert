#!/usr/bin/env python3
"""
Test runner script for TrashAlert.

This script provides a convenient way to run tests with various options.
"""

import sys
import subprocess
from pathlib import Path


def run_tests(verbose=False, coverage=False, specific_test=None):
    """
    Run the test suite.

    Args:
        verbose: Enable verbose output
        coverage: Generate coverage report
        specific_test: Run a specific test file or test function
    """
    # Build pytest command
    cmd = ["pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term"
        ])

    if specific_test:
        cmd.append(specific_test)

    # Run the tests
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    sys.exit(result.returncode)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run TrashAlert tests")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "test",
        nargs="?",
        help="Specific test file or function to run (e.g., tests/test_normalization.py)"
    )

    args = parser.parse_args()

    run_tests(
        verbose=args.verbose,
        coverage=args.coverage,
        specific_test=args.test
    )
