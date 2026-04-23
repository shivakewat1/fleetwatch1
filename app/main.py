from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from app.env import FleetWatchEnv
from app.models import Action, Observation, StateResponse, StepResponse

app = FastAPI(
    title="FleetWatch",
    description=(
        "OpenEnv-compliant RL environment for training AI oversight agents "
        "to monitor multi-agent systems and detect anomalies."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

env = FleetWatchEnv()


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/reset", response_model=Observation)
def reset(task_name: Optional[str] = Query(default=None, description="Task name to start from")):
    """
    Reset the environment and return the initial observation.

    Optionally specify a task_name to start from a specific task:
    - obvious-anomaly (easy)
    - subtle-pattern (medium)
    - adversarial-agent (hard)
    """
    try:
        observation = env.reset(task_name=task_name)
        return observation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step", response_model=StepResponse)
def step(action: Action):
    """
    Submit an action (anomaly detections) and receive the next observation and reward.

    The reward score is strictly between 0.001 and 0.999.
    If score >= 0.95, the current task is considered solved and the next task begins.
    Maximum 8 steps per task.
    """
    try:
        response = env.step(action)
        return response
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/state", response_model=StateResponse)
def state():
    """Return the current environment state including scores and task progress."""
    return env.get_state()
