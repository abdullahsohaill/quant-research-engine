"""
Quant Research Engine — A2A (Agent-to-Agent) Protocol Implementation

Implements Google's A2A specification (https://github.com/a2aproject/A2A) for
inter-agent communication. Uses JSON-RPC 2.0 over HTTP with Agent Cards for
capability discovery.

Key concepts:
  - AgentCard: JSON manifest describing an agent's capabilities, skills, endpoints
  - Task: A unit of work sent from one agent to another
  - Message/Part: Structured data exchanged between agents
  - TaskState: submitted → working → completed | failed

This is a LEAN implementation of A2A without the official SDK, demonstrating
deep understanding of the protocol internals.
"""

import json
import uuid
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# A2A CORE TYPES — per specification
# ══════════════════════════════════════════════════════════════


class TaskState(str, Enum):
    """A2A Task lifecycle states."""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Part(BaseModel):
    """A2A content part — text, file, or structured data."""
    type: str = "text"  # text | file | data
    text: Optional[str] = None
    data: Optional[dict] = None
    metadata: Optional[dict] = None


class Message(BaseModel):
    """A2A message containing one or more parts."""
    role: str  # "user" (requester) or "agent" (responder)
    parts: list[Part]
    metadata: Optional[dict] = None


class TaskStatus(BaseModel):
    """Current status of an A2A task."""
    state: TaskState
    message: Optional[Message] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Task(BaseModel):
    """
    A2A Task — the core unit of work exchanged between agents.

    Flow:
      Client agent creates a task → sends to server agent via tasks/send
      Server agent processes → updates state → returns result
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus
    history: list[Message] = []
    metadata: Optional[dict] = None


class AgentSkill(BaseModel):
    """Describes a specific capability of an agent."""
    id: str
    name: str
    description: str
    tags: list[str] = []
    examples: list[str] = []


class AgentCard(BaseModel):
    """
    A2A Agent Card — JSON manifest for agent discovery.

    Describes what the agent can do, how to reach it, and what
    input/output modalities it supports. Served at /.well-known/agent.json
    """
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    skills: list[AgentSkill] = []
    defaultInputModes: list[str] = ["text"]
    defaultOutputModes: list[str] = ["text"]
    capabilities: dict = Field(default_factory=lambda: {
        "streaming": True,
        "pushNotifications": False,
    })
    authentication: Optional[dict] = None
    provider: Optional[dict] = None


class JSONRPCRequest(BaseModel):
    """A2A JSON-RPC 2.0 request envelope."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class JSONRPCResponse(BaseModel):
    """A2A JSON-RPC 2.0 response envelope."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[dict] = None
    id: str


# ══════════════════════════════════════════════════════════════
# AGENT CARDS — Our system's agents
# ══════════════════════════════════════════════════════════════

PLANNER_AGENT_CARD = AgentCard(
    name="Planner Agent",
    description="Receives user queries, decomposes them into subtasks, and "
    "orchestrates the analysis pipeline by routing to specialized agents.",
    url="internal://planner",
    skills=[
        AgentSkill(
            id="query_decomposition",
            name="Query Decomposition",
            description="Breaks complex financial queries into atomic subtasks",
            tags=["planning", "routing", "decomposition"],
            examples=["Analyze NVIDIA vs AMD", "Best semiconductor stocks by P/E"],
        ),
    ],
)

DATA_FETCHER_AGENT_CARD = AgentCard(
    name="Data Fetcher Agent",
    description="Fetches real-time and historical financial data using MCP tools. "
    "Connects to yfinance and PostgreSQL via MCP protocol.",
    url="internal://data-fetcher",
    skills=[
        AgentSkill(
            id="stock_data_retrieval",
            name="Stock Data Retrieval",
            description="Fetches stock prices, fundamentals, earnings from yfinance",
            tags=["data", "yfinance", "MCP"],
            examples=["Get AAPL stock info", "Fetch 6-month price history for NVDA"],
        ),
        AgentSkill(
            id="sql_data_retrieval",
            name="SQL Data Retrieval",
            description="Queries the PostgreSQL database for historical analysis",
            tags=["data", "SQL", "PostgreSQL", "MCP"],
            examples=["Average P/E for tech sector", "Top 5 stocks by revenue growth"],
        ),
    ],
)

QUANT_AGENT_CARD = AgentCard(
    name="Quant Analysis Agent",
    description="Computes financial ratios, valuation metrics, and generates "
    "quantitative analysis from raw financial data.",
    url="internal://quant",
    skills=[
        AgentSkill(
            id="ratio_computation",
            name="Financial Ratio Computation",
            description="Calculates P/E, P/B, EV/EBITDA, ROE, CAGR, etc.",
            tags=["quant", "ratios", "valuation"],
        ),
        AgentSkill(
            id="peer_comparison",
            name="Peer Comparison",
            description="Benchmarks stocks against sector peers",
            tags=["comparison", "benchmarking"],
        ),
    ],
)

REPORT_WRITER_AGENT_CARD = AgentCard(
    name="Report Writer Agent",
    description="Synthesizes analysis into structured investment memos "
    "with executive summary, data tables, and recommendations.",
    url="internal://report-writer",
    skills=[
        AgentSkill(
            id="memo_generation",
            name="Investment Memo Generation",
            description="Creates professional investment memos in Markdown",
            tags=["report", "memo", "writing"],
        ),
    ],
)

CRITIC_AGENT_CARD = AgentCard(
    name="Critic Agent",
    description="Reviews investment memos for factual accuracy, internal "
    "consistency, and completeness. Uses a different LLM provider "
    "(HuggingFace) to provide independent validation.",
    url="internal://critic",
    skills=[
        AgentSkill(
            id="report_review",
            name="Report Quality Review",
            description="Cross-checks data accuracy and logical consistency",
            tags=["review", "validation", "quality"],
        ),
    ],
)

# Master registry of all agents
AGENT_REGISTRY: dict[str, AgentCard] = {
    "planner": PLANNER_AGENT_CARD,
    "data_fetcher": DATA_FETCHER_AGENT_CARD,
    "quant": QUANT_AGENT_CARD,
    "report_writer": REPORT_WRITER_AGENT_CARD,
    "critic": CRITIC_AGENT_CARD,
}


# ══════════════════════════════════════════════════════════════
# A2A MESSAGE BUS — Inter-agent communication
# ══════════════════════════════════════════════════════════════


class A2AMessageBus:
    """
    In-process A2A message bus for agent-to-agent communication.

    Implements the A2A tasks/send and tasks/get patterns for routing
    subtasks between agents. In a distributed deployment, this would
    be replaced with HTTP calls to each agent's A2A endpoint.

    Flow:
      Planner → creates Task with Message → sends to target agent
      Target agent processes → updates Task status → returns result
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._task_log: list[dict] = []

    def create_task(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Task:
        """
        Create a new A2A task (equivalent to JSON-RPC tasks/send).

        Args:
            from_agent: Source agent name
            to_agent: Target agent name
            content: Task content/instructions
            metadata: Additional context

        Returns:
            Created Task object
        """
        task = Task(
            status=TaskStatus(state=TaskState.SUBMITTED),
            history=[
                Message(
                    role="user",
                    parts=[Part(text=content)],
                    metadata={"from_agent": from_agent, "to_agent": to_agent},
                )
            ],
            metadata={
                "from_agent": from_agent,
                "to_agent": to_agent,
                **(metadata or {}),
            },
        )

        self._tasks[task.id] = task
        self._task_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "task_created",
            "task_id": task.id,
            "from": from_agent,
            "to": to_agent,
            "content_preview": content[:100],
        })

        logger.info(f"A2A Task {task.id[:8]}… | {from_agent} → {to_agent}")
        return task

    def update_task(
        self,
        task_id: str,
        state: TaskState,
        result: Optional[str] = None,
        agent_name: str = "",
    ) -> Task:
        """
        Update task status (equivalent to JSON-RPC tasks/get returning updated state).

        Args:
            task_id: Task ID to update
            state: New task state
            result: Result content
            agent_name: Agent providing the update
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = TaskStatus(
            state=state,
            message=Message(
                role="agent",
                parts=[Part(text=result or "")],
                metadata={"agent": agent_name},
            ) if result else None,
        )

        if result:
            task.history.append(
                Message(
                    role="agent",
                    parts=[Part(text=result)],
                    metadata={"agent": agent_name},
                )
            )

        self._task_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "task_updated",
            "task_id": task_id,
            "state": state.value,
            "agent": agent_name,
            "result_length": len(result) if result else 0,
        })

        logger.info(
            f"A2A Task {task_id[:8]}… | state → {state.value} "
            f"by {agent_name}"
        )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID (equivalent to JSON-RPC tasks/get)."""
        return self._tasks.get(task_id)

    def get_task_result(self, task_id: str) -> Optional[str]:
        """Extract the final result text from a completed task."""
        task = self._tasks.get(task_id)
        if not task or task.status.state != TaskState.COMPLETED:
            return None

        # Get the last agent message
        for msg in reversed(task.history):
            if msg.role == "agent" and msg.parts:
                return msg.parts[0].text
        return None

    def get_log(self) -> list[dict]:
        """Get the full A2A communication log."""
        return self._task_log

    def get_agent_cards(self) -> dict[str, dict]:
        """Get all agent cards as JSON (for /.well-known/agent.json)."""
        return {
            name: card.model_dump()
            for name, card in AGENT_REGISTRY.items()
        }
