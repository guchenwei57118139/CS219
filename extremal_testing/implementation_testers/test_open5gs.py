#!/usr/bin/env python3
"""Open5GS NRF implementation tester."""

from __future__ import annotations

import sys

import httpx

from extremal_testing.implementation_testers.base import BaseNRFTester


class Open5GSNRFTester(BaseNRFTester):
    implementation_name = "open5gs"
    default_base_url = "http://localhost:29512/nnrf-nfm/v1"
    results_prefix = "nrf_test_results_open5gs_"
    request_timeout = 10

    def create_client(self):
        return httpx.Client(http1=False, http2=True, timeout=self.request_timeout)


def run_nrf_tests(test_cases_file: str, base_url: str = Open5GSNRFTester.default_base_url) -> str:
    tester = Open5GSNRFTester(base_url=base_url)
    return tester.run_nrf_tests(test_cases_file)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_open5gs.py <test_cases_file> [base_url]")
        sys.exit(1)

    test_cases_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else Open5GSNRFTester.default_base_url
    results_file = run_nrf_tests(test_cases_file, base_url)
    print(f"Test complete. Results saved to {results_file}")


if __name__ == "__main__":
    main()
