"""
Quant Research Engine — MCP Tool Registry

Connects to MCP servers, discovers available tools, and converts
MCP tool schemas into Google GenAI function declarations.

This is the bridge between MCP protocol and the native Gemini API,
enabling tool-calling without any framework abstraction.

Architecture:
  MCP Server (FastMCP) → MCP Client → Tool Registry → GenAI function_declarations
"""

import json
import logging
import asyncio
from typing import Any, Optional

from fastmcp import Client as MCPClient

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Manages connections to MCP servers and provides tool execution.

    Connects to one or more MCP servers, discovers their tools, and:
      1. Produces GenAI-compatible function declarations for Gemini
      2. Routes tool calls from Gemini to the correct MCP server
      3. Returns results back to the orchestrator
    """

    def __init__(self):
        self._servers: dict[str, dict] = {}  # name -> {url, client, tools}
        self._tool_map: dict[str, str] = {}  # tool_name -> server_name
        self._function_declarations: list[dict] = []
        self._initialized = False

    async def register_server(self, name: str, url: str):
        """
        Register and connect to an MCP server.

        Args:
            name: Friendly name for the server (e.g., 'financial', 'postgres')
            url: MCP server URL (e.g., 'http://localhost:8001/mcp')
        """
        logger.info(f"Registering MCP server '{name}' at {url}...")

        self._servers[name] = {
            "url": url,
            "tools": [],
        }

        try:
            client = MCPClient(url)
            async with client:
                tools = await client.list_tools()

                for tool in tools:
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                    }
                    self._servers[name]["tools"].append(tool_info)
                    self._tool_map[tool.name] = name

                    # Convert to GenAI function declaration
                    func_decl = self._mcp_to_genai_declaration(tool)
                    self._function_declarations.append(func_decl)

                logger.info(
                    f"  → Registered {len(tools)} tools from '{name}': "
                    f"{[t.name for t in tools]}"
                )

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}' at {url}: {e}")
            # Register with fallback tool definitions
            raise

    def _mcp_to_genai_declaration(self, tool) -> dict:
        """
        Convert an MCP tool definition to a GenAI function declaration.

        MCP uses JSON Schema for tool parameters.
        GenAI expects OpenAPI-style parameter definitions.
        """
        # Get the input schema from the MCP tool
        schema = {}
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            schema = tool.inputSchema
        elif hasattr(tool, 'input_schema') and tool.input_schema:
            schema = tool.input_schema

        # Build the GenAI function declaration
        declaration = {
            "name": tool.name,
            "description": tool.description or f"Tool: {tool.name}",
        }

        # Convert JSON Schema properties to GenAI format
        if schema and "properties" in schema:
            params = {
                "type": "object",
                "properties": {},
                "required": schema.get("required", []),
            }

            for prop_name, prop_def in schema["properties"].items():
                param = {}
                prop_type = prop_def.get("type", "string")

                # Map JSON Schema types to OpenAPI types
                type_map = {
                    "string": "string",
                    "integer": "integer",
                    "number": "number",
                    "boolean": "boolean",
                    "array": "array",
                    "object": "object",
                }
                param["type"] = type_map.get(prop_type, "string")

                if "description" in prop_def:
                    param["description"] = prop_def["description"]
                if "enum" in prop_def:
                    param["enum"] = prop_def["enum"]
                if "default" in prop_def:
                    param["default"] = prop_def["default"]

                params["properties"][prop_name] = param

            declaration["parameters"] = params

        return declaration

    def get_genai_declarations(self) -> list[dict]:
        """
        Get all tool declarations in GenAI function_declarations format.

        Returns a list ready to be passed to:
          types.Tool(function_declarations=[...])
        """
        return self._function_declarations

    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Execute a tool call by routing to the correct MCP server.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            Tool execution result as a string
        """
        if tool_name not in self._tool_map:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        server_name = self._tool_map[tool_name]
        server_info = self._servers[server_name]

        logger.info(f"Executing tool '{tool_name}' on server '{server_name}'...")
        logger.debug(f"  Arguments: {arguments}")

        try:
            client = MCPClient(server_info["url"])
            async with client:
                result = await client.call_tool(tool_name, arguments)

            # Extract text content from MCP response
            if hasattr(result, 'content'):
                # FastMCP returns content as list of content parts
                texts = []
                for part in result:
                    if hasattr(part, 'text'):
                        texts.append(part.text)
                    else:
                        texts.append(str(part))
                result_str = "\n".join(texts)
            elif isinstance(result, list):
                texts = []
                for item in result:
                    if hasattr(item, 'text'):
                        texts.append(item.text)
                    else:
                        texts.append(str(item))
                result_str = "\n".join(texts)
            else:
                result_str = str(result)

            logger.info(f"  → Tool '{tool_name}' returned {len(result_str)} chars")
            return result_str

        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})

    def get_tool_names(self) -> list[str]:
        """Get list of all registered tool names."""
        return list(self._tool_map.keys())

    def get_server_info(self) -> dict:
        """Get summary of all registered servers and their tools."""
        return {
            name: {
                "url": info["url"],
                "tools": [t["name"] for t in info["tools"]],
            }
            for name, info in self._servers.items()
        }
