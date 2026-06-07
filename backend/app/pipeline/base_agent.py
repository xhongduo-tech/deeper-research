"""Base agent class with retry logic that never silently degrades."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.pipeline.types import AgentTask, AgentResult, PipelineError

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentResult:
        """Execute the task once. Return AgentResult with success=False on error."""

    async def run_with_retry(self, task: AgentTask, max_retries: int = 3) -> AgentResult:
        """Retry up to max_retries times, injecting prior errors into context.

        Never returns a degraded fallback result — exhausted retries raise PipelineError.
        """
        prior_errors: list[str] = []
        for attempt in range(1, max_retries + 1):
            if prior_errors:
                task.context["prior_errors"] = prior_errors
            result = await self.run(task)
            if result.success:
                return result
            error_msg = result.error or "unknown error"
            prior_errors.append(f"Attempt {attempt}: {error_msg}")
            logger.warning("[%s] attempt %d/%d failed: %s", self.name, attempt, max_retries, error_msg)

        raise PipelineError(
            phase=self.name,
            message=f"Agent failed after {max_retries} retries. Last error: {prior_errors[-1]}",
        )
