"""
Quant Research Engine — LangGraph Orchestrator

Implements a stateful graph (LangGraph) where each node is a specialized agent:
1. Planner Agent
2. Data Fetcher Agent (+ MCP)
3. SQL Analyst Agent (+ MCP)
4. Quant Agent
5. Report Writer Agent
6. Critic Agent (HuggingFace Inference API Qwen2.5-7B-Instruct)
7. Email Agent (+ MCP)

Communication between theoretical agent nodes is logged to the A2AMessageBus
conforming to the A2A spec.
"""

import json
import logging
import operator
from typing import Annotated, AsyncGenerator, TypedDict, Sequence

from google import genai
from google.genai import types
from huggingface_hub import AsyncInferenceClient
from langgraph.graph import StateGraph, START, END

from backend.config import get_settings
from backend.orchestrator.tool_registry import ToolRegistry
from backend.orchestrator.a2a_protocol import A2AMessageBus, TaskState
from backend.orchestrator.prompts import (
    PLANNER_PROMPT,
    DATA_FETCHER_PROMPT,
    SQL_ANALYST_PROMPT,
    QUANT_PROMPT,
    REPORT_WRITER_PROMPT,
    CRITIC_PROMPT,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ── 1. Define State ───────────────────────────────────────────

class AgentState(TypedDict):
    """The shared state dict passed between nodes in LangGraph."""
    query: str
    plan: list[str]
    messages: Annotated[list[str], operator.add]
    data_summary: str
    sql_summary: str
    quant_analysis: str
    report: str
    critique: str
    email_status: str


# ── 2. The Engine ─────────────────────────────────────────────

class AnalysisEngine:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.hf_client = None
        if settings.hf_token:
            self.hf_client = AsyncInferenceClient(
                token=settings.hf_token, timeout=60
            )

        self.tool_registry = ToolRegistry()
        self.bus = A2AMessageBus()
        self.graph = None
        self._initialized = False

    async def initialize(self):
        """Connect MCP servers and build the LangGraph."""
        logger.info("Initializing Agent Graph...")

        try:
            await self.tool_registry.register_server("financial", f"http://{settings.financial_mcp_host}:{settings.financial_mcp_port}/mcp")
            logger.info("  ✓ Financial MCP connected")
        except Exception as e:
            logger.warning(f"  ✗ Financial MCP unavailable: {e}")

        try:
            await self.tool_registry.register_server("postgres", f"http://{settings.postgres_mcp_host}:{settings.postgres_mcp_port}/mcp")
            logger.info("  ✓ Postgres MCP connected")
        except Exception as e:
            logger.warning(f"  ✗ Postgres MCP unavailable: {e}")

        try:
            await self.tool_registry.register_server("email", f"http://{settings.email_mcp_host}:{settings.email_mcp_port}/mcp")
            logger.info("  ✓ Email MCP connected")
        except Exception as e:
            logger.warning(f"  ✗ Email MCP unavailable: {e}")

        self._build_graph()
        self._initialized = True
        logger.info("Graph orchestrator ready.")

    def _build_graph(self):
        """Build the LangGraph state machine."""
        workflow = StateGraph(AgentState)

        workflow.add_node("planner", self._node_planner)
        workflow.add_node("data_fetcher", self._node_data_fetcher)
        workflow.add_node("sql_analyst", self._node_sql_analyst)
        workflow.add_node("quant", self._node_quant)
        workflow.add_node("report_writer", self._node_report_writer)
        workflow.add_node("critic", self._node_critic)
        workflow.add_node("email_sender", self._node_email_sender)

        # Edges define the flow
        workflow.add_edge(START, "planner")
        workflow.add_edge("planner", "data_fetcher")
        workflow.add_edge("data_fetcher", "sql_analyst")
        workflow.add_edge("sql_analyst", "quant")
        workflow.add_edge("quant", "report_writer")
        workflow.add_edge("report_writer", "critic")
        workflow.add_edge("critic", "email_sender")
        workflow.add_edge("email_sender", END)

        self.graph = workflow.compile()

    # ── Nodes ─────────────────────────────────────────────────

    async def _node_planner(self, state: AgentState) -> dict:
        """Planner Agent Node."""
        logger.info("Agent: Planner")
        task = self.bus.create_task("user", "planner", state['query'])

        config = types.GenerateContentConfig(system_instruction=PLANNER_PROMPT, temperature=0.1)
        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=[state['query']],
            config=config
        )

        try:
            # Handle markdown code blocks
            res_text = response.text.strip()
            if res_text.startswith("```json"):
                res_text = res_text[7:-3].strip()
            plan = json.loads(res_text)
        except:
            plan = ["Analyze the stock", "Write report"]

        self.bus.update_task(task.id, TaskState.COMPLETED, json.dumps(plan), "planner")
        return {"plan": plan, "messages": [f"Plan created: {len(plan)} steps"]}

    async def _node_data_fetcher(self, state: AgentState) -> dict:
        """Data Fetcher Agent Node (MCP Tool Calling)."""
        logger.info("Agent: Data Fetcher")
        task = self.bus.create_task("planner", "data_fetcher", "Fetch required financial data.")

        # Give it access to financial tools only
        declarations = [d for d in self.tool_registry.get_genai_declarations() if "sql" not in d["name"] and "email" not in d["name"]]
        tools = [types.Tool(function_declarations=declarations)] if declarations else None

        config = types.GenerateContentConfig(system_instruction=DATA_FETCHER_PROMPT, tools=tools, temperature=0.2)
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=f"Query: {state['query']}\nPlan: {state['plan']}")])]
        
        # Tool loop for Data Fetcher (simplified iter limit = 3)
        for _ in range(3):
            response = self.client.models.generate_content(model=settings.gemini_model, contents=contents, config=config)
            if not response.candidates or not response.candidates[0].content:
                break
                
            resp_content = response.candidates[0].content
            has_fc = False
            fr_parts = []
            
            for part in resp_content.parts:
                if part.function_call:
                    has_fc = True
                    fc = part.function_call
                    try:
                        result = await self.tool_registry.execute_tool(fc.name, dict(fc.args))
                    except Exception as e:
                        result = str(e)
                    fr_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
            
            if has_fc:
                contents.append(resp_content)
                contents.append(types.Content(role="user", parts=fr_parts))
            else:
                summary = response.text
                self.bus.update_task(task.id, TaskState.COMPLETED, summary, "data_fetcher")
                return {"data_summary": summary}
                
        # Fallback
        summary = response.text if response and response.text else "Failed to fetch complete data."
        self.bus.update_task(task.id, TaskState.COMPLETED, summary, "data_fetcher")
        return {"data_summary": summary}

    async def _node_sql_analyst(self, state: AgentState) -> dict:
        """SQL Analyst Agent Node (MCP Tool Calling)."""
        logger.info("Agent: SQL Analyst")
        task = self.bus.create_task("planner", "sql_analyst", "Query Postgres for historical trends.")

        # Give it access to SQL tools only
        declarations = [d for d in self.tool_registry.get_genai_declarations() if "sql" in d["name"] or "table_" in d["name"] or "sample_" in d["name"]]
        tools = [types.Tool(function_declarations=declarations)] if declarations else None

        config = types.GenerateContentConfig(system_instruction=SQL_ANALYST_PROMPT, tools=tools, temperature=0.1)
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=f"Query: {state['query']}")])]
        
        for _ in range(3):
            response = self.client.models.generate_content(model=settings.gemini_model, contents=contents, config=config)
            if not response.candidates or not response.candidates[0].content:
                break
                
            resp_content = response.candidates[0].content
            has_fc = False
            fr_parts = []
            
            for part in resp_content.parts:
                if part.function_call:
                    has_fc = True
                    fc = part.function_call
                    try:
                        result = await self.tool_registry.execute_tool(fc.name, dict(fc.args))
                    except Exception as e:
                        result = str(e)
                    fr_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
            
            if has_fc:
                contents.append(resp_content)
                contents.append(types.Content(role="user", parts=fr_parts))
            else:
                summary = response.text
                self.bus.update_task(task.id, TaskState.COMPLETED, summary, "sql_analyst")
                return {"sql_summary": summary}
                
        summary = response.text if response and response.text else "No SQL analysis generated."
        self.bus.update_task(task.id, TaskState.COMPLETED, summary, "sql_analyst")
        return {"sql_summary": summary}

    async def _node_quant(self, state: AgentState) -> dict:
        """Quant Agent Node."""
        logger.info("Agent: Quant")
        task = self.bus.create_task("planner", "quant", "Perform quantitative financial analysis.")

        prompt = f"Data Summary:\n{state.get('data_summary', '')}\n\nSQL Summary:\n{state.get('sql_summary', '')}\n\nPlease perform quantitative analysis."
        
        declarations = [d for d in self.tool_registry.get_genai_declarations() if "sql" not in d["name"] and "email" not in d["name"]]
        tools = [types.Tool(function_declarations=declarations)] if declarations else None

        config = types.GenerateContentConfig(system_instruction=QUANT_PROMPT, tools=tools, temperature=0.3)
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        
        for _ in range(3):
            response = self.client.models.generate_content(model=settings.gemini_model, contents=contents, config=config)
            if not response.candidates or not response.candidates[0].content:
                break
                
            resp_content = response.candidates[0].content
            has_fc = False
            fr_parts = []
            
            for part in resp_content.parts:
                if part.function_call:
                    has_fc = True
                    fc = part.function_call
                    try:
                        result = await self.tool_registry.execute_tool(fc.name, dict(fc.args))
                    except Exception as e:
                        result = str(e)
                    fr_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
            
            if has_fc:
                contents.append(resp_content)
                contents.append(types.Content(role="user", parts=fr_parts))
            else:
                summary = response.text
                self.bus.update_task(task.id, TaskState.COMPLETED, summary, "quant")
                return {"quant_analysis": summary}
                
        summary = response.text if response and response.text else "Failed to generate complete quant analysis."
        self.bus.update_task(task.id, TaskState.COMPLETED, summary, "quant")
        return {"quant_analysis": summary}

    async def _node_report_writer(self, state: AgentState) -> dict:
        """Report Writer Agent Node."""
        logger.info("Agent: Report Writer")
        task = self.bus.create_task("planner", "report_writer", "Draft the final investment memo.")

        prompt = (f"Original Query: {state['query']}\n\n"
                  f"Data:\n{state.get('data_summary', '')}\n\n"
                  f"SQL Insights:\n{state.get('sql_summary', '')}\n\n"
                  f"Quant Analysis:\n{state.get('quant_analysis', '')}")
                  
        config = types.GenerateContentConfig(system_instruction=REPORT_WRITER_PROMPT, temperature=0.4)
        response = self.client.models.generate_content(model=settings.gemini_model, contents=[prompt], config=config)
        
        self.bus.update_task(task.id, TaskState.COMPLETED, response.text, "report_writer")
        return {"report": response.text}

    async def _node_critic(self, state: AgentState) -> dict:
        """Critic Agent Node using HuggingFace Qwen2.5-7B."""
        logger.info("Agent: Critic (HuggingFace Qwen2.5)")
        task = self.bus.create_task("report_writer", "critic", "Review the investment memo for accuracy.")

        if not self.hf_client:
            msg = "HuggingFace Token not configured. Critic skipped."
            self.bus.update_task(task.id, TaskState.FAILED, msg, "critic")
            return {"critique": msg}

        prompt = f"{CRITIC_PROMPT}\n\nMemo to review:\n{state.get('report', '')}"
        
        try:
            # HuggingFace Qwen2.5 Chat Completion request
            messages = [{"role": "user", "content": prompt}]
            response = await self.hf_client.chat_completion(
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=messages,
                max_tokens=600,
            )
            critique = response.choices[0].message.content
            self.bus.update_task(task.id, TaskState.COMPLETED, critique, "critic")
            return {"critique": critique}
        except Exception as e:
            msg = f"Critic review failed: {str(e)}"
            logger.error(msg)
            self.bus.update_task(task.id, TaskState.FAILED, msg, "critic")
            return {"critique": msg}

    async def _node_email_sender(self, state: AgentState) -> dict:
        """Email Agent Node (MCP Tool Calling)."""
        logger.info("Agent: Email Sender")
        task = self.bus.create_task("report_writer", "email_sender", "Email the final report and critique.")

        # Check if email tool is registered
        if "send_report_email" not in self.tool_registry.get_tool_names():
            msg = "Email MCP tool not available."
            self.bus.update_task(task.id, TaskState.FAILED, msg, "email_sender")
            return {"email_status": msg}

        # Check if report looks like it requires an email (e.g. user asked for it, or default behavior)
        # We auto-email if SMTP env vars are populated. We'll attempt the tool call.
        try:
            # We assume user is the admin from config, but let's just attempt.
            admin_email = "admin@example.com" # Can be updated to parse from query
            result = await self.tool_registry.execute_tool("send_report_email", {
                "to": admin_email,
                "report": state.get('report', ''),
                "critique": state.get('critique', '')
            })
            self.bus.update_task(task.id, TaskState.COMPLETED, "Email sent", "email_sender")
            return {"email_status": result}
        except Exception as e:
            msg = f"Failed to send email: {e}"
            self.bus.update_task(task.id, TaskState.FAILED, msg, "email_sender")
            return {"email_status": msg}

    async def analyze(self, query: str, include_critique: bool = True) -> dict:
        """Run the full analysis synchronously and return the result."""
        if not self._initialized:
            await self.initialize()
            
        try:
            inputs = {"query": query, "messages": []}
            
            # Using invoke will run the full graph to completion
            final_state = await self.graph.ainvoke(inputs)
            
            return {
                "success": True,
                "report": final_state.get("report", ""),
                "critique": final_state.get("critique", ""),
                "metadata": {
                    "a2a_log": self.bus.get_log(),
                    "tool_calls": [],
                    "elapsed_seconds": 0,
                    "model": settings.gemini_model,
                    "iterations": 1,
                    "query": query
                },
                "warnings": [],
                "error": None
            }
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "warnings": []
            }


    async def analyze_stream(self, query: str) -> AsyncGenerator[dict, None]:
        """Stream the execution of the LangGraph."""
        if not self._initialized:
            await self.initialize()

        yield {"type": "status", "data": "Starting LangGraph execution..."}

        try:
            # Initial state
            inputs = {"query": query, "messages": []}
            
            # Use LangGraph's async streaming interface (stream mode="updates")
            async for chunk in self.graph.astream(inputs, stream_mode="updates"):
                for node_name, state_update in chunk.items():
                    yield {"type": "tool_call", "data": f"✓ [{node_name}] complete"}
                    
                    if node_name == "report_writer" and "report" in state_update:
                        yield {"type": "report", "data": state_update["report"]}
                    elif node_name == "critic" and "critique" in state_update:
                        yield {"type": "critique", "data": state_update["critique"]}

            yield {"type": "status", "data": "Analysis complete."}
            
            # Send final A2A log for debugging visualization
            a2a_log = self.bus.get_log()
            yield {
                "type": "metadata",
                "data": {
                    "a2a_log": a2a_log,
                    "tool_calls": [], 
                    "elapsed_seconds": 0
                }
            }

        except Exception as e:
            logger.error(f"Graph execution failed: {e}", exc_info=True)
            yield {"type": "error", "data": str(e)}


# ── Singleton Engine Instance ─────────────────────────────────
_engine_instance = None

async def get_engine() -> AnalysisEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AnalysisEngine()
    return _engine_instance
