from typing import Optional, Dict, Any, List


async def build_mcp_toolset_from_config(mcp_cfg: Dict[str, Any]) -> Optional[Any]:
    """
    Build an MCPToolset from config. Returns None when disabled or misconfigured.

    Expected schema:
    mcp:
      enabled: false
      connection:
        type: stdio | sse
        stdio:
          command: npx
          args: ["-y", "@modelcontextprotocol/server-filesystem", "/absolute/path"]
          env: { }
        sse:
          url: "https://example"
          headers: { }
      tool_filter: []
    """
    if not mcp_cfg or not mcp_cfg.get("enabled", False):
        return None

    conn_cfg = mcp_cfg.get("connection", {})
    conn_type = (conn_cfg.get("type") or "").lower()

    tool_filter: Optional[List[str]] = mcp_cfg.get("tool_filter")

    if conn_type == "stdio":
        # Import MCP classes lazily to avoid Python version issues when MCP is disabled
        from google.adk.tools.mcp_tool.mcp_toolset import (
            MCPToolset,
            StdioConnectionParams,
            StdioServerParameters,
        )
        stdio = conn_cfg.get("stdio", {})
        command = stdio.get("command")
        args = stdio.get("args", [])
        env = stdio.get("env", None)
        if not command:
            return None
        params = StdioConnectionParams(
            server_params=StdioServerParameters(command=command, args=args, env=env)
        )
        return MCPToolset(connection_params=params, tool_filter=tool_filter)

    if conn_type == "sse":
        from google.adk.tools.mcp_tool.mcp_toolset import (
            MCPToolset,
            SseConnectionParams,
        )
        sse = conn_cfg.get("sse", {})
        url = sse.get("url")
        headers = sse.get("headers", None)
        if not url:
            return None
        params = SseConnectionParams(url=url, headers=headers)
        return MCPToolset(connection_params=params, tool_filter=tool_filter)

    # Unknown connection type or missing
    return None


async def close_mcp_toolset_if_any(toolset: Optional[Any]) -> None:
    if toolset is not None:
        # MCPToolset implements async close
        await toolset.close()
