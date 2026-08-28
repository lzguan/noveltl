from src.memory.agent.dispatch.celery import CeleryMemoryAgentDispatcher
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher


def get_dispatcher() -> MemoryAgentDispatcher:
    return CeleryMemoryAgentDispatcher()
