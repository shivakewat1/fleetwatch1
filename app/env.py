from typing import Any, Dict, List, Optional
from app.models import Action, Observation, Reward, StateResponse, StepResponse
from app.tasks import get_task1, get_task2, get_task3
from app.graders import grade_task1, grade_task2, grade_task3

MAX_STEPS = 8
TASK_ORDER = ["obvious-anomaly", "subtle-pattern", "adversarial-agent"]

TASK_LOADERS = {
    "obvious-anomaly": get_task1,
    "subtle-pattern": get_task2,
    "adversarial-agent": get_task3,
}

TASK_GRADERS = {
    "obvious-anomaly": grade_task1,
    "subtle-pattern": grade_task2,
    "adversarial-agent": grade_task3,
}


class FleetWatchEnv:
    def __init__(self):
        self._task_index: int = 0
        self._step_count: int = 0
        self._done: bool = False
        self._task: Optional[Dict[str, Any]] = None
        self._task_scores: List[float] = []
        self._last_reward: Optional[Reward] = None
        self._current_task_name: Optional[str] = None

    def reset(self, task_name: Optional[str] = None) -> Observation:
        """Reset the environment. Optionally specify a task by name."""
        self._step_count = 0
        self._done = False
        self._last_reward = None

        if task_name is not None:
            if task_name not in TASK_ORDER:
                raise ValueError(f"Unknown task: {task_name}. Valid tasks: {TASK_ORDER}")
            self._task_index = TASK_ORDER.index(task_name)
            self._task_scores = []
        else:
            self._task_index = 0
            self._task_scores = []

        self._current_task_name = TASK_ORDER[self._task_index]
        self._task = TASK_LOADERS[self._current_task_name]()
        return self._build_observation()

    def step(self, action: Action) -> StepResponse:
        """Process an action and return the next observation, reward, and done flag."""
        if self._done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")
        if self._task is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        self._step_count += 1

        # Grade the action
        grader = TASK_GRADERS[self._current_task_name]
        reward = grader(action, self._task)
        self._last_reward = reward

        # Early exit if score >= 0.95
        task_complete = reward.score >= 0.95 or self._step_count >= MAX_STEPS

        if task_complete:
            self._task_scores.append(reward.score)
            # Move to next task
            self._task_index += 1
            if self._task_index >= len(TASK_ORDER):
                self._done = True
                obs = self._build_observation(final=True)
            else:
                self._current_task_name = TASK_ORDER[self._task_index]
                self._task = TASK_LOADERS[self._current_task_name]()
                self._step_count = 0
                obs = self._build_observation()
        else:
            obs = self._build_observation(previous_feedback=reward.feedback)

        return StepResponse(
            observation=obs,
            reward=reward,
            done=self._done,
            info={
                "task_complete": task_complete,
                "step_count": self._step_count,
                "task_index": self._task_index,
                "current_task": self._current_task_name if not self._done else "done",
            },
        )

    def get_state(self) -> StateResponse:
        """Return the current environment state."""
        total_score = sum(self._task_scores) / len(self._task_scores) if self._task_scores else 0.0
        return StateResponse(
            task_id=self._current_task_name or "not_started",
            step_count=self._step_count,
            done=self._done,
            total_score=round(total_score, 4),
            task_scores=self._task_scores,
            current_task_index=self._task_index,
        )

    def _build_observation(
        self, previous_feedback: Optional[str] = None, final: bool = False
    ) -> Observation:
        if final or self._task is None:
            return Observation(
                task_id="done",
                agent_logs=[],
                authorized_actions=[],
                task_context="All tasks completed.",
                task_description="Episode complete.",
                step_count=self._step_count,
                previous_feedback=previous_feedback,
            )

        return Observation(
            task_id=self._task["task_id"],
            agent_logs=self._task["logs"],
            authorized_actions=self._task["authorized_actions"],
            task_context=self._task["task_context"],
            task_description=self._task["task_description"],
            step_count=self._step_count,
            previous_feedback=previous_feedback,
        )
