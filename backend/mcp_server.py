"""
MCP Server for Production Line Simulator
Exposes simulator functions as MCP tools using FastMCP.

Usage:
    # stdio transport (default)
    python -m backend.mcp_server
    
    # HTTP transport
    python -m backend.mcp_server --transport http --port 8001

Integration with LangChain MCP Adapters:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    
    client = MultiServerMCPClient({
        "production": {
            "command": "python",
            "args": ["-m", "backend.mcp_server"],
            "transport": "stdio",
        }
    })
    tools = await client.get_tools()
"""
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from .simulator import simulator

# Create FastMCP server instance
mcp = FastMCP("production-line-simulator")


# ─────────────────────────────────────────────────────────────────────────────
# Station Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_all_stations() -> list:
    """Get data for all production stations including status, throughput, efficiency, temperature, pressure, and maintenance info."""
    return simulator.get_all_stations()


@mcp.tool()
def get_station(station_id: str) -> dict:
    """Get detailed data for a specific production station by ID.
    
    Args:
        station_id: The ID of the station (e.g., ST001, ST002)
    """
    return simulator.get_station(station_id)


@mcp.tool()
def get_station_status(station_id: str) -> dict:
    """Get status information for a specific station (status, uptime, efficiency).
    
    Args:
        station_id: The ID of the station
    """
    return simulator.get_station_status(station_id)


@mcp.tool()
def update_station_status(station_id: str, status: str) -> dict:
    """Update a station's status.
    
    Args:
        station_id: The ID of the station to update
        status: New status (running, idle, maintenance, error)
    """
    return simulator.update_station_status(station_id, status)


@mcp.tool()
def get_stations_by_status(status: str) -> list:
    """Get all stations with a specific status.
    
    Args:
        status: Status to filter by (running, idle, maintenance, error)
    """
    return simulator.get_stations_by_status(status)


# ─────────────────────────────────────────────────────────────────────────────
# Metrics Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_production_metrics() -> dict:
    """Get overall production metrics including total units produced, efficiency, downtime, quality rate, and energy consumption."""
    return simulator.get_production_metrics()


@mcp.tool()
def calculate_oee(station_id: Optional[str] = None) -> dict:
    """Calculate Overall Equipment Effectiveness (OEE) for a station or overall production line.
    
    Args:
        station_id: Optional station ID. If not provided, calculates overall OEE
    """
    return simulator.calculate_oee(station_id)


@mcp.tool()
def find_bottleneck(stations: Optional[List[str]] = None) -> dict:
    """Identify the production bottleneck (station with lowest throughput).
    
    Args:
        stations: Optional list of station IDs to analyze. If not provided, analyzes all running stations.
    """
    return simulator.find_bottleneck(stations)


# ─────────────────────────────────────────────────────────────────────────────
# Maintenance Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_maintenance_schedule() -> list:
    """Get maintenance schedule showing days since last maintenance and priority for each station."""
    return simulator.get_maintenance_schedule()


# ─────────────────────────────────────────────────────────────────────────────
# Production Run Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_recent_runs(limit: int = 5) -> list:
    """Get recent production runs with scrap and cycle time details.
    
    Args:
        limit: Maximum number of runs to return (default: 5)
    """
    return simulator.get_recent_runs(limit)


# ─────────────────────────────────────────────────────────────────────────────
# Alarm Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_alarm_log(limit: int = 10) -> list:
    """Get recent alarm log entries.
    
    Args:
        limit: Maximum number of alarms to return (default: 10)
    """
    return simulator.get_alarm_log(limit)


# ─────────────────────────────────────────────────────────────────────────────
# Energy Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_station_energy(station_id: str) -> dict:
    """Get energy snapshot for a station.
    
    Args:
        station_id: Station ID to query energy for
    """
    return simulator.get_station_energy(station_id)


# ─────────────────────────────────────────────────────────────────────────────
# Quality Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_scrap_summary() -> dict:
    """Get scrap totals, scrap rate, and top defect codes."""
    return simulator.get_scrap_summary()


@mcp.tool()
def get_product_mix() -> list:
    """Get mix of produced units by product."""
    return simulator.get_product_mix()


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Production Line MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type (default: stdio)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)"
    )
    
    args = parser.parse_args()
    mcp.run(transport=args.transport)
