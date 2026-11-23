from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.dispatch.taskiq_dispatcher import TaskiqMemoryAgentDispatcher


def get_dispatcher() -> MemoryAgentDispatcher:
    return TaskiqMemoryAgentDispatcher()
