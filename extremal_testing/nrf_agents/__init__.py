"""NRF agents package."""

__all__ = ["NRFExtremalTestingAgent"]


def __getattr__(name: str):
    if name == "NRFExtremalTestingAgent":
        from extremal_testing.nrf_agents.workflow.orchestrator import NRFExtremalTestingAgent

        return NRFExtremalTestingAgent
    raise AttributeError(name)
