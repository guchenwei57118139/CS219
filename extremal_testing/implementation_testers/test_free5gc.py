#!/usr/bin/env python3
"""Free5GC NRF implementation tester."""

from __future__ import annotations

import sys

import requests

from extremal_testing.implementation_testers.base import BaseNRFTester


class Free5GCNRFTester(BaseNRFTester):
    implementation_name = "free5gc"
    default_base_url = "http://localhost:29510/nnrf-nfm/v1"
    results_prefix = "nrf_test_results_free5gc_"
    request_timeout = 10

    def create_client(self):
        return requests.Session()


def run_nrf_tests(test_cases_file: str, base_url: str = Free5GCNRFTester.default_base_url) -> str:
    tester = Free5GCNRFTester(base_url=base_url)
    return tester.run_nrf_tests(test_cases_file)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_free5gc.py <test_cases_file> [base_url]")
        sys.exit(1)

    test_cases_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else Free5GCNRFTester.default_base_url
    results_file = run_nrf_tests(test_cases_file, base_url)
    print(f"Test complete. Results saved to {results_file}")


if __name__ == "__main__":
    main()
