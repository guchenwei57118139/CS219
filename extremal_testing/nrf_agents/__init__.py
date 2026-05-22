"""NRF agents package."""

__all__ = ["NRFExtremalTestingAgent"]


def __getattr__(name: str):
    if name == "NRFExtremalTestingAgent":
        from nrf_agents.workflow.orchestrator import NRFExtremalTestingAgent

        return NRFExtremalTestingAgent
    raise AttributeError(name)
