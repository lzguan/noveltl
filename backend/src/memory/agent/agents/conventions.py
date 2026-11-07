"""Conventions agent: proposes novel-wide translation conventions for a chapter range."""

from pydantic_ai import Agent

from src.memory.agent.capabilities.conventions import ConventionsOutput
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.types import ModelName


def create_conventions_agent(model_name: ModelName) -> Agent[MemAgentDeps, ConventionsOutput]:
    raise NotImplementedError("The conventions agent is not implemented yet")
