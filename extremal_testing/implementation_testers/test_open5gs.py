#!/usr/bin/env python3
"""Open5GS NRF implementation tester."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.implementation_testers.base import BaseNRFTester


class Open5GSNRFTester(BaseNRFTester):
    implementation_name = "open5gs"
    default_base_url = "http://localhost:29512/nnrf-nfm/v1"
    results_prefix = "nrf_test_results_open5gs_"
    request_timeout = 10
    container_name = "open5gs-nrf"
    restart_timeout = 30
    deterministic_crash_threshold = 3

    def __init__(self, base_url=None):
        super().__init__(base_url=base_url)
        self._recovery_disabled = False
        self._consecutive_deterministic_crashes = 0

    def create_client(self):
        return httpx.Client(http1=False, http2=True, timeout=self.request_timeout)

    def _summarize_process_text(self, value) -> str:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        text = str(value or "").strip()
        return " ".join(text.split())[:500]

    def _disable_recovery(self, reason: str) -> None:
        print(reason, flush=True)
        print(
            "[Open5GS] Automatic Docker recovery is disabled for the rest of this run because the previous restart attempt failed.",
            flush=True,
        )
        self._recovery_disabled = True

    def recover_from_transport_failure(self) -> bool:
        if self._recovery_disabled:
            return False

        print(
            f"[Open5GS] Transport failure detected. Restarting Docker container '{self.container_name}'.",
            flush=True,
        )
        try:
            subprocess.run(
                ["docker", "restart", self.container_name],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.restart_timeout,
            )
        except FileNotFoundError:
            self._disable_recovery(
                "[Open5GS] Docker recovery failed: docker command was not found."
            )
            return False
        except subprocess.TimeoutExpired as exc:
            output = self._summarize_process_text(exc.output)
            stderr = self._summarize_process_text(exc.stderr)
            detail = f" stdout={output}" if output else ""
            detail += f" stderr={stderr}" if stderr else ""
            self._disable_recovery(
                f"[Open5GS] Docker recovery failed: docker restart timed out after {self.restart_timeout}s.{detail}"
            )
            return False
        except subprocess.CalledProcessError as exc:
            stdout = self._summarize_process_text(exc.stdout)
            stderr = self._summarize_process_text(exc.stderr)
            detail = f" stdout={stdout}" if stdout else ""
            detail += f" stderr={stderr}" if stderr else ""
            self._disable_recovery(
                f"[Open5GS] Docker recovery failed: docker restart exited with code {exc.returncode}.{detail}"
            )
            return False
        except Exception:
            self._disable_recovery(
                "[Open5GS] Docker recovery failed: unexpected error while restarting the container."
            )
            return False

        print(
            f"[Open5GS] Docker container '{self.container_name}' restarted. Waiting for NRF readiness at {self.base_url}.",
            flush=True,
        )
        if self.wait_for_service():
            print(
                "[Open5GS] NRF readiness check passed. Continuing tests.",
                flush=True,
            )
            return True

        print(
            f"[Open5GS] Docker container '{self.container_name}' restarted, but NRF did not become reachable at {self.base_url}. Continuing with the observed test failure.",
            flush=True,
        )
        return False

    def after_recovery_attempt(self, original_execution, recovered_execution) -> None:
        if self.execution_has_transport_failure(recovered_execution):
            self._consecutive_deterministic_crashes += 1
            if self._consecutive_deterministic_crashes >= self.deterministic_crash_threshold:
                print(
                    "[Open5GS] Multiple tests are deterministically crashing the NRF after successful restart. Disabling automatic restarts for the rest of this operation.",
                    flush=True,
                )
                self._recovery_disabled = True
            return

        self._consecutive_deterministic_crashes = 0


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
