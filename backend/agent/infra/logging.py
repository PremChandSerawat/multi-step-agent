"""
Agent Logging Module

Provides structured logging for tracking agent execution:
- Phase/step calls with arguments
- Tool calls with inputs/outputs
- LLM calls with prompts/responses
- Timing information
- Error tracking
"""
from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from functools import wraps

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LogType(str, Enum):
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    STATE_UPDATE = "state_update"
    ERROR = "error"
    ROUTING = "routing"


@dataclass
class LogEntry:
    """A single log entry for agent execution."""
    timestamp: str
    log_type: str
    phase: str
    message: str
    duration_ms: Optional[float] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class AgentLogger:
    """
    Structured logger for agent execution tracking.
    
    Usage:
        logger = AgentLogger(thread_id="thread-123")
        
        with logger.phase("validation"):
            logger.log_input({"question": "..."})
            # ... do work ...
            logger.log_output({"status": "valid"})
        
        logger.print_summary()
    """
    
    def __init__(
        self, 
        thread_id: str = "default",
        log_to_console: bool = True,
        log_level: LogLevel = LogLevel.INFO,
        max_data_length: int = 500
    ):
        self.thread_id = thread_id
        self.log_to_console = log_to_console
        self.log_level = log_level
        self.max_data_length = max_data_length
        self.entries: List[LogEntry] = []
        self._phase_stack: List[tuple] = []  # (phase_name, start_time)
        self._logger = logging.getLogger(f"agent.{thread_id[:20]}")
        
    def _now(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
    
    def _truncate(self, data: Any) -> Any:
        """Truncate large data for logging."""
        if data is None:
            return None
        text = json.dumps(data, default=str) if not isinstance(data, str) else data
        if len(text) > self.max_data_length:
            return text[:self.max_data_length] + f"... [truncated {len(text) - self.max_data_length} chars]"
        return data
    
    def _add_entry(self, entry: LogEntry) -> None:
        """Add a log entry and optionally print to console."""
        self.entries.append(entry)
        
        if self.log_to_console:
            level_map = {
                LogType.ERROR: logging.ERROR,
                LogType.PHASE_START: logging.INFO,
                LogType.PHASE_END: logging.INFO,
                LogType.TOOL_CALL: logging.INFO,
                LogType.TOOL_RESULT: logging.INFO,
                LogType.LLM_CALL: logging.DEBUG,
                LogType.LLM_RESPONSE: logging.DEBUG,
            }
            log_level = level_map.get(LogType(entry.log_type), logging.INFO)
            
            # Format the log message
            msg_parts = [f"[{entry.log_type.upper()}]", f"[{entry.phase}]", entry.message]
            if entry.duration_ms is not None:
                msg_parts.append(f"({entry.duration_ms:.1f}ms)")
            
            self._logger.log(log_level, " ".join(msg_parts))
            
            # Log input/output at debug level
            if entry.input_data and log_level <= logging.DEBUG:
                self._logger.debug(f"  Input: {self._truncate(entry.input_data)}")
            if entry.output_data and log_level <= logging.DEBUG:
                self._logger.debug(f"  Output: {self._truncate(entry.output_data)}")
            if entry.error:
                self._logger.error(f"  Error: {entry.error}")
    
    # =========================================================================
    # Phase Logging
    # =========================================================================
    
    def phase_start(self, phase: str, input_data: Optional[Dict] = None) -> None:
        """Log the start of a phase."""
        self._phase_stack.append((phase, time.time()))
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.PHASE_START.value,
            phase=phase,
            message=f"Starting {phase}",
            input_data=self._truncate(input_data) if input_data else None
        ))
    
    def phase_end(self, phase: str, output_data: Optional[Dict] = None, error: Optional[str] = None) -> None:
        """Log the end of a phase."""
        duration_ms = None
        if self._phase_stack and self._phase_stack[-1][0] == phase:
            _, start_time = self._phase_stack.pop()
            duration_ms = (time.time() - start_time) * 1000
        
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.PHASE_END.value,
            phase=phase,
            message=f"Completed {phase}" if not error else f"Failed {phase}",
            duration_ms=duration_ms,
            output_data=self._truncate(output_data) if output_data else None,
            error=error
        ))
    
    class PhaseContext:
        """Context manager for phase logging."""
        def __init__(self, logger: 'AgentLogger', phase: str, input_data: Optional[Dict] = None):
            self.logger = logger
            self.phase = phase
            self.input_data = input_data
            self.output_data = None
            self.error = None
            
        def __enter__(self):
            self.logger.phase_start(self.phase, self.input_data)
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_val:
                self.error = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
            self.logger.phase_end(self.phase, self.output_data, self.error)
            return False
        
        def set_output(self, data: Dict) -> None:
            self.output_data = data
    
    def phase(self, phase: str, input_data: Optional[Dict] = None) -> PhaseContext:
        """Context manager for phase logging."""
        return self.PhaseContext(self, phase, input_data)
    
    # =========================================================================
    # Tool Logging
    # =========================================================================
    
    def log_tool_call(self, tool_name: str, arguments: Dict[str, Any], phase: str = "execution") -> None:
        """Log a tool call with its arguments."""
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.TOOL_CALL.value,
            phase=phase,
            message=f"Calling tool: {tool_name}",
            input_data={"tool": tool_name, "arguments": self._truncate(arguments)}
        ))
    
    def log_tool_result(
        self, 
        tool_name: str, 
        result: Any, 
        success: bool = True,
        duration_ms: Optional[float] = None,
        error: Optional[Exception | str] = None,
        phase: str = "execution"
    ) -> None:
        """Log a tool result with complete error if failed."""
        error_str = None
        if error:
            if isinstance(error, Exception):
                error_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            else:
                error_str = str(error)
        
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.TOOL_RESULT.value,
            phase=phase,
            message=f"Tool {tool_name}: {'success' if success else 'failed'}",
            duration_ms=duration_ms,
            output_data={"tool": tool_name, "result": self._truncate(result)} if success else None,
            error=error_str
        ))
    
    # =========================================================================
    # LLM Logging
    # =========================================================================
    
    def log_llm_call(self, purpose: str, messages: List[Dict], phase: str = "llm") -> None:
        """Log an LLM call with its messages."""
        # Extract just the key info from messages
        summary = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]
            summary.append({"role": role, "content_preview": content})
        
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.LLM_CALL.value,
            phase=phase,
            message=f"LLM call: {purpose}",
            input_data={"purpose": purpose, "messages": summary}
        ))
    
    def log_llm_response(
        self, 
        purpose: str, 
        response: str,
        duration_ms: Optional[float] = None,
        phase: str = "llm"
    ) -> None:
        """Log an LLM response."""
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.LLM_RESPONSE.value,
            phase=phase,
            message=f"LLM response: {purpose}",
            duration_ms=duration_ms,
            output_data={"response_preview": self._truncate(response)}
        ))
    
    # =========================================================================
    # State Logging
    # =========================================================================
    
    def log_state_update(self, field: str, value: Any, phase: str = "state") -> None:
        """Log a state update."""
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.STATE_UPDATE.value,
            phase=phase,
            message=f"State update: {field}",
            output_data={field: self._truncate(value)}
        ))
    
    def log_routing(self, from_node: str, to_node: str, reason: str = "") -> None:
        """Log a routing decision."""
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.ROUTING.value,
            phase="routing",
            message=f"Route: {from_node} -> {to_node}",
            metadata={"from": from_node, "to": to_node, "reason": reason}
        ))
    
    # =========================================================================
    # Error Logging
    # =========================================================================
    
    def log_error(self, message: str, error: Exception, phase: str = "error") -> None:
        """Log an error with full traceback."""
        full_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        self._add_entry(LogEntry(
            timestamp=self._now(),
            log_type=LogType.ERROR.value,
            phase=phase,
            message=message,
            error=full_traceback
        ))
    
    # =========================================================================
    # Summary & Export
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the agent execution."""
        phases = {}
        errors = []
        tools_called = []
        llm_calls = 0
        total_duration = 0
        
        for entry in self.entries:
            if entry.log_type == LogType.PHASE_END.value:
                phases[entry.phase] = {
                    "duration_ms": entry.duration_ms,
                    "success": entry.error is None
                }
                if entry.duration_ms:
                    total_duration += entry.duration_ms
            
            if entry.log_type == LogType.ERROR.value:
                errors.append({"phase": entry.phase, "error": entry.error})
            
            if entry.log_type == LogType.TOOL_CALL.value:
                tool_info = entry.input_data or {}
                tools_called.append(tool_info.get("tool", "unknown"))
            
            if entry.log_type == LogType.LLM_CALL.value:
                llm_calls += 1
        
        return {
            "thread_id": self.thread_id,
            "total_entries": len(self.entries),
            "total_duration_ms": total_duration,
            "phases": phases,
            "tools_called": tools_called,
            "llm_calls": llm_calls,
            "errors": errors,
            "success": len(errors) == 0
        }
    
    def print_summary(self) -> None:
        """Print a formatted summary to console."""
        summary = self.get_summary()
        print("\n" + "=" * 60)
        print("AGENT EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Thread ID: {summary['thread_id']}")
        print(f"Total Duration: {summary['total_duration_ms']:.1f}ms")
        print(f"Total Log Entries: {summary['total_entries']}")
        print(f"LLM Calls: {summary['llm_calls']}")
        print(f"Tools Called: {', '.join(summary['tools_called']) or 'None'}")
        print(f"Success: {'✓' if summary['success'] else '✗'}")
        
        print("\nPhases:")
        for phase, info in summary['phases'].items():
            status = "✓" if info['success'] else "✗"
            duration = f"{info['duration_ms']:.1f}ms" if info['duration_ms'] else "N/A"
            print(f"  {status} {phase}: {duration}")
        
        if summary['errors']:
            print("\nErrors:")
            for err in summary['errors']:
                print(f"  [{err['phase']}] {err['error']}")
        
        print("=" * 60 + "\n")
    
    def to_json(self) -> str:
        """Export all log entries as JSON."""
        return json.dumps({
            "thread_id": self.thread_id,
            "entries": [e.to_dict() for e in self.entries],
            "summary": self.get_summary()
        }, indent=2, default=str)
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """Get all log entries as dicts."""
        return [e.to_dict() for e in self.entries]


# Global logger instance (can be replaced per-request)
_current_logger: Optional[AgentLogger] = None


def get_logger() -> Optional[AgentLogger]:
    """Get the current request's logger."""
    return _current_logger


def set_logger(logger: AgentLogger) -> None:
    """Set the current request's logger."""
    global _current_logger
    _current_logger = logger


def create_logger(thread_id: str, **kwargs) -> AgentLogger:
    """Create and set a new logger for a request."""
    logger = AgentLogger(thread_id=thread_id, **kwargs)
    set_logger(logger)
    return logger

