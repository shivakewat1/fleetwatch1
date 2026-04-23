from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentLog(BaseModel):
    agent_id: str
    timestamp: str
    action_type: str  # "read" | "write" | "delete" | "api_call" | "send_message"
    target: str
    authorized: bool
    metadata: Dict[str, Any] = {}


class Observation(BaseModel):
    task_id: str
    agent_logs: List[AgentLog]
    authorized_actions: List[str]
    task_context: str
    task_description: str
    step_count: int
    previous_feedback: Optional[str] = None


class Anomaly(BaseModel):
    log_index: int
    agent_id: str
    action_type: str
    severity: str  # "low" | "medium" | "high" | "critical"
    description: str
    recommendation: str


class Action(BaseModel):
    anomalies: List[Anomaly]
    overall_risk: str  # "safe" | "low" | "medium" | "high" | "critical"
    summary: str


class Reward(BaseModel):
    score: float = Field(ge=0.001, le=0.999)
    breakdown: Dict[str, Any]
    feedback: str


class StepResponse(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: Dict[str, Any] = {}


class StateResponse(BaseModel):
    task_id: str
    step_count: int
    done: bool
    total_score: float
    task_scores: List[float]
    current_task_index: int
