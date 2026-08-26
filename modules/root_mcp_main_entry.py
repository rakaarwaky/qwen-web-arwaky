"""qwen-web MCP server entry point (MCP 2.0.0 API).

Root layer: bootstraps the MCP server over stdio using mcp.server.Server.
Tools are registered and delegate to the shared core aggregate.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

import mcp.types as types
from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
from mcp_types._types import ServerCapabilities, ToolsCapability

from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.root_core_container import SharedContainer
from modules.mcp.src.surface_mcp_tool_command import McpToolCommand
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
from modules.shared.src.utility_core_version import get_package_version

# ─── Logging setup ──────────────────────────────────────────────────────────

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("qwen-mcp")

# ─── Container & tool instance ──────────────────────────────────────────────

_container: McpToolCommand | None = None


def _get_tools() -> McpToolCommand:
    """Return the MCP surface tool command, wiring the container once."""
    global _container
    if _container is None:
        shared = SharedContainer()
        shared.wire()
        _container = McpToolCommand(
            direct=shared.agent_direct_prompt_orchestrator,
            file_only=shared.agent_prompt_file_orchestrator,
            attachment=shared.agent_attachment_prompt_orchestrator,
            session=shared.agent_session_orchestrator,
            setup=shared.agent_setup_orchestrator,
            workspace=shared.workspace,
            jobs=shared.agent_job_orchestrator,
        )
    return _container


# ─── Async tool wrappers ────────────────────────────────────────────────────

# Map MCP tool names -> McpToolCommand method names
_TOOL_METHOD_MAP: dict[str, str] = {
    "process_direct_prompt": "process_direct_prompt",
    "process_prompt_file_only": "process_prompt_file_only",
    "process_prompt_with_attachment": "process_prompt_with_attachment",
    "get_job_status": "get_job_status",
    "list_jobs": "list_jobs",
    "check_session": "check_session",
    "delete_session": "delete_session",
    "setup_session": "setup_session",
    "init": "init_workspace",
    "init_workspace": "init_workspace",
}


def _async_tool(name: str) -> Callable[..., Awaitable[Sequence[str]]]:
    """Wrap a sync core method as an async MCP tool handler."""

    async def handler(*args: Any, **kwargs: Any) -> Sequence[str]:
        method_name = _TOOL_METHOD_MAP.get(name, name)

        def invoke() -> str:
            tools = _get_tools()
            return str(getattr(tools, method_name)(*args, **kwargs))

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, invoke)

    return handler


# ─── MCP Tool definitions ───────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="init",
        description="Initialize workspace directory structure, .agents/skills/qwen-web/SKILL.md guide, sample prompt/file, and .gitignore.",
        input_schema={
            "type": "object",
            "properties": {
                "target_dir": {
                    "type": "string",
                    "description": "Target directory to initialize (default: current working directory).",
                    "default": ".",
                    "examples": ["/home/user/my-workspace"],
                },
            },
        },
    ),
    Tool(
        name="process_direct_prompt",
        description="Process a direct text prompt string to chat.qwen.ai and return the AI answer. Requires a valid login session; call setup_session if not authenticated.",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt text to send to Qwen.",
                    "examples": ["Summarize the key differences between SQL and NoSQL databases."],
                },
                "timeout_sec": {
                    "type": "integer",
                    "description": "Maximum seconds to wait for the assistant response.",
                    "default": 120,
                    "minimum": 1,
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run the browser headlessly (True) or with visible UI (False).",
                    "default": True,
                },
            },
            "required": ["prompt"],
        },
    ),
    Tool(
        name="process_prompt_file_only",
        description="Process a single Markdown prompt file (no attachment) on chat.qwen.ai. By default, dispatches asynchronously in background and returns a job_id to prevent MCP client timeouts.",
        input_schema={
            "type": "object",
            "properties": {
                "input_file": {
                    "type": "string",
                    "description": "Absolute or relative path to the Markdown prompt file.",
                    "examples": ["/home/user/prompts/analysis.md"],
                },
                "output_file": {
                    "type": "string",
                    "description": "Destination path for the AI response output (optional).",
                    "default": None,
                    "examples": ["/home/user/output/analysis_output.md"],
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run the browser headlessly (True) or with visible UI (False).",
                    "default": True,
                },
                "async_run": {
                    "type": "boolean",
                    "description": "Run asynchronously in background to avoid MCP timeout (default: True).",
                    "default": True,
                },
            },
            "required": ["input_file"],
        },
    ),
    Tool(
        name="process_prompt_with_attachment",
        description="Process a Markdown prompt file with a document attachment on chat.qwen.ai. Attachment must be a supported text/document format (.txt, .md, .pdf, code files) and at most 100 MB. Archives and binaries (.zip, .tar, .gz, .tgz, .7z, .rar, .bz2, .xz, .exe, .bin, .iso, .dmg, .so, .dll, .dylib) are rejected. By default, dispatches asynchronously in background and returns a job_id to prevent MCP client timeouts.",
        input_schema={
            "type": "object",
            "properties": {
                "prompt_file": {
                    "type": "string",
                    "description": "Absolute or relative path to the Markdown prompt file.",
                    "examples": ["/home/user/prompts/analyze_doc.md"],
                },
                "attachment_file": {
                    "type": "string",
                    "description": "Path to the document to attach. Must exist, be readable, not exceed 100 MB, and not be an archive/binary format.",
                    "examples": ["/home/user/docs/report.pdf"],
                },
                "output_file": {
                    "type": "string",
                    "description": "Destination path for the AI response output (optional).",
                    "default": None,
                    "examples": ["/home/user/output/analysis_output.md"],
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run the browser headlessly (True) or with visible UI (False).",
                    "default": True,
                },
                "async_run": {
                    "type": "boolean",
                    "description": "Run asynchronously in background to avoid MCP timeout (default: True).",
                    "default": True,
                },
            },
            "required": ["prompt_file", "attachment_file"],
        },
    ),
    Tool(
        name="get_job_status",
        description="Query the current status, timing, progress, and result preview of an asynchronous background job.",
        input_schema={
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID returned from process_prompt_file_only or process_prompt_with_attachment.",
                    "examples": ["file_20260827_051800_abc123"],
                },
            },
            "required": ["job_id"],
        },
    ),
    Tool(
        name="list_jobs",
        description="List recently submitted asynchronous background prompt processing jobs.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of recent jobs to return (default: 10).",
                    "default": 10,
                    "minimum": 1,
                },
            },
        },
    ),
    Tool(
        name="check_session",
        description="Check status and validity of saved browser session tokens. Returns session_valid flag and the recommended next action.",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="delete_session",
        description="Delete saved browser session tokens. Requires confirm=True parameter to proceed.",
        input_schema={
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "boolean",
                    "description": "Must be True to confirm deletion of saved session tokens.",
                    "default": False,
                },
            },
        },
    ),
    Tool(
        name="setup_session",
        description="Launch a visible browser on chat.qwen.ai for manual login / session setup. Call this first when check_session reports an invalid or missing session.",
        input_schema={"type": "object", "properties": {}},
    ),
]

# Build async handlers for each tool — extract name from Tool objects
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[Sequence[str]]]] = {
    tool.name: _async_tool(tool.name) for tool in TOOLS
}

# Async tool functions for direct surface calls
init = _async_tool("init")
process_direct_prompt = _async_tool("process_direct_prompt")
process_prompt_file_only = _async_tool("process_prompt_file_only")
process_prompt_with_attachment = _async_tool("process_prompt_with_attachment")
get_job_status = _async_tool("get_job_status")
list_jobs = _async_tool("list_jobs")
check_session = _async_tool("check_session")
delete_session = _async_tool("delete_session")
setup_session = _async_tool("setup_session")

GENERATED_TOOLS = TOOL_HANDLERS

MCP_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "process_direct_prompt",
        "method": "process_direct_prompt",
        "doc": "Process a direct text prompt string to chat.qwen.ai and return the AI answer.",
        "params": [("prompt", "str", True), ("timeout_sec", "int", False, 120), ("headless", "bool", False, True)],
    },
    {
        "name": "process_prompt_file_only",
        "method": "process_prompt_file_only",
        "doc": "Process a single Markdown prompt file (no attachment) on chat.qwen.ai.",
        "params": [
            ("input_file", "str", True),
            ("output_file", "Any", False, None),
            ("headless", "bool", False, True),
            ("async_run", "bool", False, True),
        ],
    },
    {
        "name": "process_prompt_with_attachment",
        "method": "process_prompt_with_attachment",
        "doc": "Process a Markdown prompt file with a document attachment on chat.qwen.ai.",
        "params": [
            ("prompt_file", "str", True),
            ("attachment_file", "str", True),
            ("output_file", "Any", False, None),
            ("headless", "bool", False, True),
            ("async_run", "bool", False, True),
        ],
    },
    {
        "name": "get_job_status",
        "method": "get_job_status",
        "doc": "Query the current status and result preview of an asynchronous background job.",
        "params": [("job_id", "str", True)],
    },
    {
        "name": "list_jobs",
        "method": "list_jobs",
        "doc": "List recently submitted asynchronous background prompt processing jobs.",
        "params": [("limit", "int", False, 10)],
    },
    {
        "name": "setup_session",
        "method": "setup_session",
        "doc": "Launch visible browser on chat.qwen.ai for manual login / session setup.",
        "params": [],
    },
]


# ─── Server runner ──────────────────────────────────────────────────────────


def run_mcp_server() -> None:
    """Run the MCP server over stdio."""
    ObservabilitySetup(DEFAULT_LOG).setup_observability()

    async def serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            capabilities = ServerCapabilities(tools=ToolsCapability())
            init_opts = InitializationOptions(
                server_name="Qwen-Web",
                server_version=get_package_version(),
                capabilities=capabilities,
            )
            server = Server("Qwen-Web")

            async def handle_list_tools(
                context: Any, params: types.PaginatedRequestParams | None = None
            ) -> types.ListToolsResult:
                return types.ListToolsResult(tools=TOOLS)

            async def handle_call_tool(context: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
                handler = TOOL_HANDLERS.get(params.name)
                if handler is None:
                    raise ValueError(f"Unknown tool: {params.name}")
                try:
                    result = await handler(**(params.arguments or {}))
                    if isinstance(result, str):
                        content_blocks = [types.TextContent(type="text", text=result)]
                    else:
                        content_blocks = [types.TextContent(type="text", text=str(r)) for r in result]
                    return types.CallToolResult(content=cast(Any, content_blocks), is_error=False)
                except Exception as exc:
                    log.error("Tool execution error: %s", exc)
                    return types.CallToolResult(
                        content=cast(Any, [types.TextContent(type="text", text=f"Error: {exc}")]),
                        is_error=True,
                    )

            async def handle_list_resources(
                context: Any, params: types.PaginatedRequestParams | None = None
            ) -> types.ListResourcesResult:
                return types.ListResourcesResult(resources=[])

            async def handle_read_resource(
                context: Any, params: types.ReadResourceRequestParams
            ) -> types.ReadResourceResult:
                return types.ReadResourceResult(contents=[])

            server.add_request_handler("tools/list", types.PaginatedRequestParams, handle_list_tools)
            server.add_request_handler("tools/call", types.CallToolRequestParams, handle_call_tool)
            server.add_request_handler("resources/list", types.PaginatedRequestParams, handle_list_resources)
            server.add_request_handler("resources/read", types.ReadResourceRequestParams, handle_read_resource)

            await server.run(read_stream, write_stream, initialization_options=init_opts)

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        log.info("MCP server shutting down")


def main() -> None:
    """Entry point for the qwen-web MCP server."""
    run_mcp_server()


if __name__ == "__main__":
    main()
