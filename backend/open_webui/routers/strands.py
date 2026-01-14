import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4
import asyncio
import threading
import copy
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from open_webui.models.users import UserModel
from open_webui.models.models import Models
from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.env import SRC_LOG_LEVELS

# Import Strands components directly
try:
    import boto3
    from strands import Agent
    from strands.models import BedrockModel
    from strands.tools import tool
    import requests
except ImportError as e:
    logging.error(f"Failed to import Strands dependencies: {e}")
    Agent = None
    BedrockModel = None
    tool = None

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("STRANDS", logging.INFO))

router = APIRouter()

# Configuration
AWS_PROFILE = os.environ.get('AWS_PROFILE', 'nSightS3Profile')
AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')
MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
CLICKHOUSE_MCP_BASE_URL = os.environ.get('CLICKHOUSE_MCP_BASE_URL', 'http://172.31.2.111:7070/')

DEFAULT_SYSTEM_PROMPT = """You are a System Performance Analyst. You can do following tasks:
- Analyze system performance data stored in a ClickHouse database.
- Answer questions related to system performance based on the data in the database.
- Generate reports on system performance metrics.
- Provide insights and recommendations based on the performance data.
- Write SQL queries to extract relevant performance data from the ClickHouse database.
- Help users understand the performance characteristics of their systems.
- The ClickHouse database contains tables with system performance data, including metrics such as CPU usage, memory usage, disk I/O, and network activity.
- The tables may also contain timestamps, hostnames, and other relevant metadata.
- Use nSight_all database for your analysis.
- The tables contains information about iis logs
- The schema of the tables may vary, so you should be prepared to explore the database structure and understand the relationships between different tables.
- When a user asks a question, you should first analyze the question to determine what information is needed to answer it.
- You should not make up any information. If you don't know the answer, you should say you don't know.
- You should match full customer names when filtering data.
- Ignore ODataService urls when filtering data.

Available ClickHouse MCP Tools:
- list_databases: List available ClickHouse databases
- list_tables: List available ClickHouse tables in a database, including schema, comment, row count, and column count
- run_select_query: Run a SELECT query in a ClickHouse database

at the end of result, always add nice words to appreciate the user to use nSight AI system.
"""

# Use environment variable or default
SYSTEM_PROMPT = os.environ.get('STRANDS_SYSTEM_PROMPT', DEFAULT_SYSTEM_PROMPT)

# Global agent instance
_agent_instance = None
_clickhouse_client = None
_agent_tools = []
_execution_log = []  # Track execution steps for thinking process
_tool_call_counts = {}  # Track how many times each tool is called

_execution_log_lock = threading.Lock()
_execution_listener_lock = threading.Lock()
_execution_event_listeners: List[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []


def register_execution_listener(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
    """Register an async listener for execution log updates."""
    with _execution_listener_lock:
        _execution_event_listeners.append((loop, queue))


def clear_execution_listener(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
    """Remove an execution listener."""
    with _execution_listener_lock:
        if (loop, queue) in _execution_event_listeners:
            _execution_event_listeners.remove((loop, queue))


def _notify_execution_listeners(event: dict):
    """Dispatch execution log events to registered async listeners."""
    with _execution_listener_lock:
        listeners = list(_execution_event_listeners)

    for loop, queue in listeners:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, copy.deepcopy(event))
        except RuntimeError:
            # Event loop might be closed; ignore
            continue

class ClickHouseMCPClient:
    """ClickHouse MCP Client for database operations"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        log.info(f"[CLICKHOUSE MCP] Initialized client")
        log.info(f"[CLICKHOUSE MCP] Base URL: {base_url}")
    
    def list_databases(self) -> Dict[str, Any]:
        """List available ClickHouse databases"""
        try:
            log.info(f"[CLICKHOUSE MCP] Calling list_databases")
            log.info(f"[CLICKHOUSE MCP] Endpoint: {self.base_url}/list_databases")
            
            response = self.session.post(f"{self.base_url}/list_databases")
            response.raise_for_status()
            result = response.json()
            
            # Handle both list and dict responses from MCP server
            if isinstance(result, list):
                # MCP server returned a list directly
                databases = result
                result = {"databases": databases}
                log.info(f"[CLICKHOUSE MCP] Converted list response to dict format")
            
            # Log response details
            if "error" in result:
                log.error(f"[CLICKHOUSE MCP] ✗ list_databases returned error: {result['error']}")
            else:
                db_count = len(result.get("databases", []))
                log.info(f"[CLICKHOUSE MCP] ✓ list_databases completed: {db_count} database(s)")
                if db_count > 0:
                    log.info(f"[CLICKHOUSE MCP] Databases: {', '.join(result.get('databases', []))}")
            
            return result
        except Exception as e:
            error_msg = f"Failed to list databases: {str(e)}"
            log.error(f"[CLICKHOUSE MCP] ✗ {error_msg}")
            return {"error": error_msg}
    
    def list_tables(self, database: str, like: Optional[str] = None, not_like: Optional[str] = None) -> Dict[str, Any]:
        """List available ClickHouse tables in a database"""
        try:
            log.info(f"[CLICKHOUSE MCP] Calling list_tables")
            log.info(f"[CLICKHOUSE MCP] Database: {database}")
            if like:
                log.info(f"[CLICKHOUSE MCP] LIKE filter: {like}")
            if not_like:
                log.info(f"[CLICKHOUSE MCP] NOT LIKE filter: {not_like}")
            
            payload = {"database": database}
            if like:
                payload["like"] = like
            if not_like:
                payload["not_like"] = not_like
            
            response = self.session.post(
                f"{self.base_url}/list_tables",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle both list and dict responses from MCP server
            if isinstance(result, list):
                # MCP server returned a list directly
                tables = result
                result = {"tables": tables}
                log.info(f"[CLICKHOUSE MCP] Converted list response to dict format")
            
            # Log response details
            if "error" in result:
                log.error(f"[CLICKHOUSE MCP] ✗ list_tables returned error: {result['error']}")
            else:
                table_count = len(result.get("tables", []))
                log.info(f"[CLICKHOUSE MCP] ✓ list_tables completed: {table_count} table(s)")
                if table_count > 0 and table_count <= 10:
                    tables_list = result.get('tables', [])
                    # Handle both string table names and dict table objects
                    table_names = [t.get('name', t) if isinstance(t, dict) else str(t) for t in tables_list]
                    log.info(f"[CLICKHOUSE MCP] Tables: {', '.join(table_names)}")
                elif table_count > 10:
                    tables_list = result.get('tables', [])[:10]
                    table_names = [t.get('name', t) if isinstance(t, dict) else str(t) for t in tables_list]
                    log.info(f"[CLICKHOUSE MCP] First 10 tables: {', '.join(table_names)}")
            
            return result
        except Exception as e:
            error_msg = f"Failed to list tables: {str(e)}"
            log.error(f"[CLICKHOUSE MCP] ✗ {error_msg}")
            return {"error": error_msg}
    
    def run_select_query(self, query: str) -> Dict[str, Any]:
        """Run a SELECT query in a ClickHouse database"""
        try:
            log.info(f"[CLICKHOUSE MCP] Executing SQL query")
            # Log truncated query for readability
            if len(query) > 200:
                log.info(f"[CLICKHOUSE QUERY] Query (truncated): {query[:200]}...")
                log.info(f"[CLICKHOUSE QUERY] Full query length: {len(query)} characters")
            else:
                log.info(f"[CLICKHOUSE QUERY] Query: {query}")
            
            # Add query to execution log for DB Queries tab
            global _execution_log
            with _execution_log_lock:
                query_event = {
                    "type": "clickhouse_query",
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "description": f"ClickHouse Query: {query[:100]}..." if len(query) > 100 else f"ClickHouse Query: {query}"
                }
                _execution_log.append(query_event)
                log.info(f"[CLICKHOUSE QUERY] Added query to execution log")
            
            _notify_execution_listeners(query_event)
            
            payload = {"query": query}
            response = self.session.post(
                f"{self.base_url}/run_select_query",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle both list and dict responses from MCP server
            if isinstance(result, list):
                # MCP server returned raw rows as a list
                # Wrap in expected format
                result = {"rows": result, "columns": []}
                log.info(f"[CLICKHOUSE MCP] Converted list response to dict format")
            
            # Log response details
            if "error" in result:
                log.error(f"[CLICKHOUSE MCP] ✗ Query execution failed: {result['error']}")
            else:
                row_count = len(result.get("rows", []))
                col_count = len(result.get("columns", []))
                log.info(f"[CLICKHOUSE MCP] ✓ Query executed successfully")
                log.info(f"[CLICKHOUSE MCP] Results: {row_count} row(s), {col_count} column(s)")
                if col_count > 0:
                    log.info(f"[CLICKHOUSE MCP] Columns: {', '.join(result.get('columns', []))}")
            
            return result
        except Exception as e:
            error_msg = f"Failed to run query: {str(e)}"
            log.error(f"[CLICKHOUSE MCP] ✗ {error_msg}")
            return {"error": error_msg}

def log_tool_call(tool_name: str, args: dict = None):
    """Log a tool call to the execution log"""
    global _execution_log, _tool_call_counts

    with _execution_log_lock:
        # Update call count
        _tool_call_counts[tool_name] = _tool_call_counts.get(tool_name, 0) + 1

        # Log the event
        event = {
            "type": "tool_call",
            "tool_name": tool_name,
            "args": args or {},
            "timestamp": datetime.now().isoformat(),
            "call_number": _tool_call_counts[tool_name]
        }
        _execution_log.append(event)

    # Enhanced console logging
    log.info(f"[STRANDS TOOL] ▶ Calling tool '{tool_name}' (attempt #{_tool_call_counts[tool_name]})")
    if args:
        log.info(f"[STRANDS TOOL] Arguments: {json.dumps(args, indent=2, default=str)}")
    
    _notify_execution_listeners(event)

def log_tool_result(tool_name: str, result: Any, error: str = None):
    """Log a tool result to the execution log"""
    global _execution_log

    with _execution_log_lock:
        event = {
            "type": "tool_result",
            "tool_name": tool_name,
            "success": error is None,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        _execution_log.append(event)

    # Enhanced console logging
    if error:
        log.error(f"[STRANDS TOOL] ✗ Tool '{tool_name}' failed")
        log.error(f"[STRANDS TOOL] Error: {error}")
    else:
        log.info(f"[STRANDS TOOL] ✓ Tool '{tool_name}' completed successfully")
        # Log result summary (truncate if too long)
        result_str = str(result)
        if len(result_str) > 500:
            log.info(f"[STRANDS TOOL] Result (truncated): {result_str[:500]}...")
            log.info(f"[STRANDS TOOL] Result length: {len(result_str)} characters")
        else:
            log.info(f"[STRANDS TOOL] Result: {result_str}")

    _notify_execution_listeners(event)

def reset_execution_tracking():
    """Reset execution tracking for a new request"""
    global _execution_log, _tool_call_counts
    with _execution_log_lock:
        # Log summary of previous execution if there was any activity
        if _execution_log or _tool_call_counts:
            log.info("[STRANDS TRACKING] Previous execution summary:")
            log.info(f"[STRANDS TRACKING] - Total events: {len(_execution_log)}")
            log.info(f"[STRANDS TRACKING] - Total tool calls: {sum(_tool_call_counts.values())}")
            for tool_name, count in _tool_call_counts.items():
                log.info(f"[STRANDS TRACKING]   • {tool_name}: {count}")
        
        # Reset tracking
        _execution_log = []
        _tool_call_counts = {}
        log.info("[STRANDS TRACKING] ✓ Execution tracking reset for new request")

class StreamingOutputCapture:
    """Custom file-like object that streams output to logging in real-time"""
    
    def __init__(self, logger_func, prefix):
        self.logger_func = logger_func
        self.prefix = prefix
        self.buffer = ""
        self.current_reasoning = ""
        self.tool_counter = 0
    
    def write(self, text):
        """Write text and log complete lines immediately"""
        if text:
            self.buffer += text
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                if line.strip():
                    self.logger_func(f"{self.prefix} {line.strip()}")
                    # Extract reasoning for chain of thought
                    self._extract_reasoning(line.strip())
        return len(text)
    
    def _extract_reasoning(self, line):
        """Extract reasoning from agent output for chain of thought logging"""
        global _execution_log
        
        # Skip tool usage patterns - we don't want these in chain of thought
        if line.startswith("Tool #"):
            # Don't add tool calls to chain of thought, just log them
            if ":" in line:
                tool_name = line.split(":", 1)[1].strip()
                log.info(f"[STRANDS TOOL_USAGE] Tool call detected: {tool_name}")
            return
        
        # Detect reasoning patterns in agent output - only include actual reasoning
        if any(keyword in line.lower() for keyword in [
            "let me", "now let me", "i'll", "i will", "let's", "first", "next", 
            "then", "now i", "i need to", "to analyze", "to check", "to find",
            "excellent", "perfect", "good", "great", "based on", "looking at",
            "the analysis", "from the", "this shows", "we can see", "it appears"
        ]):
            # This looks like reasoning text
            self.current_reasoning = line
            
            # Log reasoning as chain of thought
            with _execution_log_lock:
                event = {
                    "type": "reasoning_step", 
                    "description": f"Agent reasoning: {line}",
                    "reasoning_text": line,
                    "timestamp": datetime.now().isoformat()
                }
                _execution_log.append(event)
                log.info(f"[STRANDS CHAIN_OF_THOUGHT] Agent reasoning: {line}")
            
            _notify_execution_listeners(event)
    
    def flush(self):
        """Flush any remaining content in buffer"""
        if self.buffer.strip():
            self.logger_func(f"{self.prefix} {self.buffer.strip()}")
            self._extract_reasoning(self.buffer.strip())
            self.buffer = ""

def capture_agent_output(func, *args, **kwargs):
    """Capture stdout/stderr from Strands agent and stream to logging in real-time"""
    # Create streaming capture objects
    stdout_capture = StreamingOutputCapture(log.info, "[STRANDS AGENT OUTPUT]")
    stderr_capture = StreamingOutputCapture(log.error, "[STRANDS AGENT ERROR]")
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            result = func(*args, **kwargs)
        
        # Flush any remaining content
        stdout_capture.flush()
        stderr_capture.flush()
        
        return result
        
    except Exception as e:
        # Flush any remaining content even if there was an exception
        stdout_capture.flush()
        stderr_capture.flush()
        raise e

def initialize_agent(system_prompt: Optional[str] = None):
    """Initialize the Strands agent with tools
    
    Args:
        system_prompt: Optional system prompt to use. If None, uses the default prompt.
    """
    global _agent_instance, _clickhouse_client, _agent_tools
    
    # Use provided system prompt or fall back to environment/default
    prompt_to_use = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    
    # If a custom system prompt is provided, don't use the cached instance
    if _agent_instance is not None and system_prompt is None:
        return _agent_instance
    
    if Agent is None or BedrockModel is None or tool is None:
        log.error("Strands dependencies not available")
        return None
    
    try:
        # Configure AWS
        os.environ['AWS_PROFILE'] = AWS_PROFILE
        os.environ['AWS_DEFAULT_REGION'] = AWS_DEFAULT_REGION
        
        log.info(f"Configured AWS Profile: {AWS_PROFILE}")
        log.info(f"Configured AWS Region: {AWS_DEFAULT_REGION}")
        log.info(f"Using Bedrock Model: {MODEL_ID}")
        
        # Initialize BedrockModel
        model_id = BedrockModel(model_id=MODEL_ID, max_tokens=64000)
        log.info("BedrockModel initialized successfully")
        
        # Initialize ClickHouse client
        _clickhouse_client = ClickHouseMCPClient(CLICKHOUSE_MCP_BASE_URL)
        
        # Create tools for the agent
        @tool
        def list_databases():
            """List available ClickHouse databases"""
            log_tool_call("list_databases")
            try:
                result = _clickhouse_client.list_databases()
                log_tool_result("list_databases", result)
                return result
            except Exception as e:
                log_tool_result("list_databases", None, str(e))
                raise

        @tool
        def list_tables(database: str, like: str = None, not_like: str = None):
            """List available ClickHouse tables in a database, including schema, comment, row count, and column count
            
            Args:
                database: Database name
                like: Filter tables with LIKE pattern (optional)
                not_like: Filter tables with NOT LIKE pattern (optional)
            """
            log_tool_call("list_tables", {"database": database, "like": like, "not_like": not_like})
            try:
                result = _clickhouse_client.list_tables(database, like, not_like)
                log_tool_result("list_tables", result)
                return result
            except Exception as e:
                log_tool_result("list_tables", None, str(e))
                raise

        @tool
        def run_select_query(query: str):
            """Run a SELECT query in a ClickHouse database
            
            Args:
                query: SQL SELECT query to execute
            """
            log_tool_call("run_select_query", {"query": query[:100]})  # Log first 100 chars of query
            try:
                result = _clickhouse_client.run_select_query(query)
                log_tool_result("run_select_query", result)
                return result
            except Exception as e:
                log_tool_result("run_select_query", None, str(e))
                raise

        # Store tools for introspection
        _agent_tools = [list_databases, list_tables, run_select_query]
        
        # Create agent with tools
        log.info("Creating Strands Agent with tools...")
        log.info(f"[STRANDS AGENT] Initializing with configuration:")
        log.info(f"[STRANDS AGENT] - Model ID: {MODEL_ID}")
        log.info(f"[STRANDS AGENT] - AWS Profile: {AWS_PROFILE}")
        log.info(f"[STRANDS AGENT] - AWS Region: {AWS_DEFAULT_REGION}")
        log.info(f"[STRANDS AGENT] - ClickHouse URL: {CLICKHOUSE_MCP_BASE_URL}")
        log.info(f"[STRANDS AGENT] - Tools: {[tool.__name__ for tool in _agent_tools]}")
        
        agent = Agent(
            model=model_id,
            system_prompt=prompt_to_use,
            tools=_agent_tools
        )
        log.info("[STRANDS AGENT] ✓ Agent setup completed successfully")
        log.info(f"[STRANDS AGENT] System prompt length: {len(prompt_to_use)} characters")
        
        # Always cache the agent instance so get_agent_internals() can access it
        _agent_instance = agent
        
        return agent
        
    except Exception as e:
        log.error(f"Failed to initialize Strands agent: {e}")
        return None

class AgentInternals(BaseModel):
    """Model for agent internal state"""
    tools: List[Dict[str, Any]]
    system_prompt: str
    model_info: Dict[str, Any]
    chain_of_thought: List[Dict[str, Any]]
    execution_log: Optional[List[Dict[str, Any]]] = []
    metrics: Optional[Dict[str, Any]] = {}

class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = "user"
    content: str

class ChatRequest(BaseModel):
    """Chat completion request"""
    model: str = "strands-ai"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.1
    stream: Optional[bool] = True  # Enable streaming by default
    include_internals: Optional[bool] = False

class ChatResponse(BaseModel):
    """Chat completion response"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, int]] = None
    internals: Optional[AgentInternals] = None

def get_agent_internals(system_prompt: Optional[str] = None) -> Optional[AgentInternals]:
    """Get current agent internal state with execution tracking
    
    Args:
        system_prompt: Optional system prompt to include in internals. If None, uses the agent's actual system prompt.
    """
    global _agent_instance, _agent_tools, _execution_log, _tool_call_counts
    
    if _agent_instance is None:
        log.warning("[STRANDS INTERNALS] Agent not initialized")
        return None
    
    # Use provided system prompt, or get the actual system prompt from the agent instance, or fall back to default
    if system_prompt is not None:
        prompt_to_show = system_prompt
    elif hasattr(_agent_instance, 'system_prompt') and _agent_instance.system_prompt:
        prompt_to_show = _agent_instance.system_prompt
    else:
        prompt_to_show = SYSTEM_PROMPT
    
    try:
        with _execution_log_lock:
            execution_log_snapshot = list(_execution_log)
            tool_call_counts_snapshot = dict(_tool_call_counts)
        
        # Extract tool information with call counts
        tools_info = []
        for tool_func in _agent_tools:
            # Get annotations and convert type objects to strings
            annotations = getattr(tool_func, '__annotations__', {})
            parameters = {
                param_name: str(param_type) if isinstance(param_type, type) else param_type
                for param_name, param_type in annotations.items()
            }
            
            tool_name = tool_func.__name__
            tool_info = {
                "name": tool_name,
                "description": tool_func.__doc__ or "",
                "parameters": parameters,
                "call_count": tool_call_counts_snapshot.get(tool_name, 0)
            }
            tools_info.append(tool_info)
        
        # Get model information
        model_info = {
            "model_id": MODEL_ID,
            "aws_profile": AWS_PROFILE,
            "aws_region": AWS_DEFAULT_REGION,
            "max_tokens": 64000
        }
        
        # Build chain of thought from execution log - only include reasoning steps
        chain_of_thought = []
        step_number = 1
        for event in execution_log_snapshot:
            if event["type"] == "reasoning_step":
                # Only include reasoning steps from agent output
                step = {
                    "description": event.get("description", "Agent reasoning"),
                    "timestamp": event["timestamp"],
                    "reasoning": event.get("reasoning_text", event.get("tool_context", ""))
                }
                chain_of_thought.append(step)
                step_number += 1
        
        # Calculate metrics
        total_tool_calls = sum(tool_call_counts_snapshot.values())
        metrics = {
            "tool_calls": total_tool_calls,
            "thinking_steps": len(chain_of_thought)
        }
        
        # Log internals summary to console
        log.info(f"[STRANDS INTERNALS] Agent state snapshot:")
        log.info(f"[STRANDS INTERNALS] - Total tool calls: {total_tool_calls}")
        log.info(f"[STRANDS INTERNALS] - Thinking steps: {len(chain_of_thought)}")
        log.info(f"[STRANDS INTERNALS] - Tools with activity: {len([t for t in tools_info if t['call_count'] > 0])}/{len(tools_info)}")
        for tool in tools_info:
            if tool['call_count'] > 0:
                log.info(f"[STRANDS INTERNALS] • {tool['name']}: {tool['call_count']} call(s)")
        
        # Log chain of thought details to file
        if chain_of_thought:
            log.info(f"[STRANDS CHAIN_OF_THOUGHT] Recording {len(chain_of_thought)} thinking steps:")
            for i, step in enumerate(chain_of_thought, 1):
                step_desc = step.get('description', 'No description')
                step_reasoning = step.get('reasoning', '')
                step_timestamp = step.get('timestamp', 'No timestamp')
                log.info(f"[STRANDS CHAIN_OF_THOUGHT] {step_desc}")
                if step_reasoning:
                    # Truncate reasoning if too long for readability
                    reasoning_text = step_reasoning[:200] + '...' if len(step_reasoning) > 200 else step_reasoning
                    #log.info(f"[STRANDS CHAIN_OF_THOUGHT] Reasoning: {reasoning_text}")
        
        internals = AgentInternals(
            tools=tools_info,
            system_prompt=prompt_to_show,
            model_info=model_info,
            chain_of_thought=chain_of_thought,
            execution_log=execution_log_snapshot,  # Include full execution log
            metrics=metrics
        )
        
        return internals
    except Exception as e:
        log.error(f"[STRANDS INTERNALS] Error getting agent internals: {e}")
        import traceback
        log.error(f"[STRANDS INTERNALS] Traceback: {traceback.format_exc()}")
        return None

def extract_user_question(messages: List[ChatMessage]) -> str:
    """Extract the last user message"""
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return ""

def build_conversation_context(messages: List[ChatMessage]) -> str:
    """Build full conversation context including history"""
    conversation = []
    for message in messages:
        role = message.role.upper()
        content = message.content
        conversation.append(f"{role}: {content}")
    return "\n\n".join(conversation)

@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    """Get Strands AI configuration"""
    return {
        "ENABLE_STRANDS_AI": True,
        "AWS_PROFILE": AWS_PROFILE,
        "AWS_REGION": AWS_DEFAULT_REGION,
        "MODEL_ID": MODEL_ID,
        "CLICKHOUSE_MCP_BASE_URL": CLICKHOUSE_MCP_BASE_URL
    }

@router.post("/config/update")
async def update_config(
    request: Request, 
    form_data: Dict[str, Any], 
    user=Depends(get_admin_user)
):
    """Update Strands AI configuration"""
    global AWS_PROFILE, AWS_DEFAULT_REGION, MODEL_ID, CLICKHOUSE_MCP_BASE_URL
    global _agent_instance, _clickhouse_client
    
    # Update configuration
    if "AWS_PROFILE" in form_data:
        AWS_PROFILE = form_data["AWS_PROFILE"]
        os.environ["AWS_PROFILE"] = AWS_PROFILE
    
    if "AWS_REGION" in form_data:
        AWS_DEFAULT_REGION = form_data["AWS_REGION"]
        os.environ["AWS_DEFAULT_REGION"] = AWS_DEFAULT_REGION
    
    if "MODEL_ID" in form_data:
        MODEL_ID = form_data["MODEL_ID"]
        os.environ["BEDROCK_MODEL_ID"] = MODEL_ID
    
    if "CLICKHOUSE_MCP_BASE_URL" in form_data:
        CLICKHOUSE_MCP_BASE_URL = form_data["CLICKHOUSE_MCP_BASE_URL"]
        os.environ["CLICKHOUSE_MCP_BASE_URL"] = CLICKHOUSE_MCP_BASE_URL
    
    # Reset agent to pick up new configuration
    _agent_instance = None
    _clickhouse_client = None
    
    return {
        "ENABLE_STRANDS_AI": True,
        "AWS_PROFILE": AWS_PROFILE,
        "AWS_REGION": AWS_DEFAULT_REGION,
        "MODEL_ID": MODEL_ID,
        "CLICKHOUSE_MCP_BASE_URL": CLICKHOUSE_MCP_BASE_URL
    }

@router.get("/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    """Get available Strands AI models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "strands-ai",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "strands-ai",
                "permission": [],
                "root": "strands-ai",
                "parent": None,
                "description": "nSight Strands AI Agent"
            }
        ]
    }

def _format_status_message(description: str, *, done: bool = False, stage: str = "strands_thinking", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a standardized status payload."""
    payload = {
        "action": stage,
        "description": description,
        "done": done,
        "timestamp": datetime.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


def _format_execution_status(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert an execution log event into a status payload."""
    event_type = event.get("type")
    tool_name = event.get("tool_name")
    timestamp = event.get("timestamp")

    if event_type == "tool_call":
        call_number = event.get("call_number")
        description = f"Running tool '{tool_name}' (attempt {call_number})"
        extra = {
            "tool_name": tool_name,
            "call_number": call_number,
            "timestamp": timestamp,
        }
        return _format_status_message(description, done=False, extra=extra)

    if event_type == "tool_result":
        success = event.get("success", False)
        description = (
            f"Tool '{tool_name}' completed successfully"
            if success
            else f"Tool '{tool_name}' failed"
        )
        extra = {
            "tool_name": tool_name,
            "timestamp": timestamp,
            "success": success,
            "error": event.get("error"),
        }
        return _format_status_message(description, done=True, extra=extra)

    return None


async def stream_strands_response(
    agent,
    conversation_context: str,
    request_id: str,
    model: str,
    start_time,
    include_internals: bool = False,
    system_prompt: Optional[str] = None
):
    """Stream the Strands AI response in real-time"""
    
    log.info(f"[STRANDS STREAM] Starting stream for request {request_id}")
    log.info(f"[STRANDS STREAM] Conversation context length: {len(conversation_context)} characters")
    log.info(f"[STRANDS STREAM] Context preview: {conversation_context[:200]}{'...' if len(conversation_context) > 200 else ''}")
    log.info(f"[STRANDS STREAM] Include internals: {include_internals}")

    loop = asyncio.get_running_loop()
    execution_queue: asyncio.Queue = asyncio.Queue()
    register_execution_listener(loop, execution_queue)

    def _status_event(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps({'type': 'status', 'data': payload})}\n\n"

    def _internals_event(internals_data: Dict[str, Any]) -> str:
        """Send incremental thinking process updates"""
        chunk_data = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(start_time.timestamp()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "strands_internals": internals_data
                },
                "finish_reason": None
            }],
            "strands_internals": internals_data
        }
        return f"data: {json.dumps(chunk_data)}\n\n"

    # Initial status updates
    log.info(f"[STRANDS STREAM] Sending initialization status")
    yield _status_event(_format_status_message("Initializing Strands agent...", done=True))

    try:
        agent_task = asyncio.create_task(asyncio.to_thread(capture_agent_output, agent, conversation_context))
        log.info(f"[STRANDS STREAM] Agent task created")
        yield _status_event(_format_status_message("Analyzing request with Strands tools...", done=True))

        # Send initial empty internals to show the component
        if include_internals:
            log.info(f"[STRANDS STREAM] Sending initial internals")
            initial_internals = {
                "chain_of_thought": [],
                "tools": [],
                "execution_log": [],
                "streaming": True
            }
            yield _internals_event(initial_internals)

        # Stream execution updates while the agent runs
        event_count = 0
        while True:
            if agent_task.done():
                log.info(f"[STRANDS STREAM] Agent task completed after {event_count} events")
                break

            try:
                event = await asyncio.wait_for(execution_queue.get(), timeout=0.2)
                event_count += 1
                log.info(f"[STRANDS STREAM] Event #{event_count}: {event.get('type')} - {event.get('tool_name', 'N/A')}")
            except asyncio.TimeoutError:
                continue

            status_payload = _format_execution_status(event)
            if status_payload:
                yield _status_event(status_payload)

            # Send incremental thinking process updates
            if include_internals:
                current_internals = get_agent_internals(system_prompt=system_prompt)
                if current_internals:
                    internals_dict = json.loads(json.dumps(current_internals.model_dump(), default=str))
                    internals_dict["streaming"] = True
                    
                    # Log chain of thought updates during streaming
                    chain_of_thought = internals_dict.get('chain_of_thought', [])
                    if chain_of_thought:
                        log.info(f"[STRANDS STREAM] Chain of thought update: {len(chain_of_thought)} steps")
                        for i, step in enumerate(chain_of_thought[-3:], max(1, len(chain_of_thought) - 2)):  # Log last 3 steps
                            step_desc = step.get('description', 'No description')
                            log.info(f"[STRANDS STREAM] Recent step {i}: {step_desc}")
                            

                    
                    log.info(f"[STRANDS STREAM] Sending internals update: {len(chain_of_thought)} steps")
                    yield _internals_event(internals_dict)
            #log.info(f"[STRANDS STREAM] Agent response--00: \r\n{str(await agent_task)}")
        # Drain any remaining events emitted right as the agent completes
        drain_count = 0
        while not execution_queue.empty():
            event = execution_queue.get_nowait()
            drain_count += 1
            log.info(f"[STRANDS STREAM] Draining event #{drain_count}: {event.get('type')} - {event.get('tool_name', 'N/A')}")
            status_payload = _format_execution_status(event)
            if status_payload:
                yield _status_event(status_payload)
        
        if drain_count > 0:
            log.info(f"[STRANDS STREAM] Drained {drain_count} remaining events")

        # Retrieve agent response
        answer = await agent_task
        answer_text = str(answer)
        log.info(f"[STRANDS STREAM] Agent response length: {len(answer_text)} characters")
        
        # Log the final agent response content
        if len(answer_text) > 1000:
            log.info(f"[STRANDS STREAM] Final agent response (truncated): {answer_text[:1000]}...")
        else:
            log.info(f"[STRANDS STREAM] Final agent response: {answer_text}")

        yield _status_event(_format_status_message("Generating final response...", done=False))

        # Stream the response in chunks (simulating typing effect)
        chunk_size = 50  # characters per chunk
        total_chunks = (len(answer_text) + chunk_size - 1) // chunk_size
        log.info(f"[STRANDS STREAM] Streaming response in {total_chunks} chunks")
        
        for i in range(0, len(answer_text), chunk_size):
            chunk = answer_text[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1

            chunk_data = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(start_time.timestamp()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant" if i == 0 else None,
                        "content": chunk
                    },
                    "finish_reason": None
                }]
            }

            if chunk_num % 10 == 0:  # Log every 10th chunk to avoid spam
                log.info(f"[STRANDS STREAM] Sent chunk {chunk_num}/{total_chunks}")
            
            yield f"data: {json.dumps(chunk_data)}\n\n"
            await asyncio.sleep(0.05)  # Small delay for smooth streaming

        # Send final internals with streaming=False
        if include_internals:
            final_internals = get_agent_internals(system_prompt=system_prompt)
            if final_internals:
                internals_dict = json.loads(json.dumps(final_internals.model_dump(), default=str))
                internals_dict["streaming"] = False
                log.info(f"[STRANDS STREAM] Sending final internals")
                log.info(f"[STRANDS STREAM] - Tools used: {len([t for t in internals_dict.get('tools', []) if t.get('call_count', 0) > 0])}")
                log.info(f"[STRANDS STREAM] - Total tool calls: {sum(t.get('call_count', 0) for t in internals_dict.get('tools', []))}")
                log.info(f"[STRANDS STREAM] - Thinking steps: {len(internals_dict.get('chain_of_thought', []))}")
                yield _internals_event(internals_dict)

        final_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(start_time.timestamp()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield _status_event(_format_status_message("Strands analysis complete", done=True))
        yield "data: [DONE]\n\n"

        processing_time = (datetime.now() - start_time).total_seconds()
        log.info(f"[STRANDS STREAM] ✓ Request {request_id}: Streaming completed in {processing_time:.2f}s")

    except Exception as e:
        log.error(f"[STRANDS STREAM] ✗ Request {request_id}: Streaming error: {e}")
        import traceback
        log.error(f"[STRANDS STREAM] Traceback: {traceback.format_exc()}")
        
        error_status = _format_status_message(
            f"Strands agent encountered an error: {str(e)}",
            done=True,
            extra={"error": str(e)}
        )
        yield _status_event(error_status)

        error_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(start_time.timestamp()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": f"\n\nError: {str(e)}"
                },
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    finally:
        clear_execution_listener(loop, execution_queue)
        log.info(f"[STRANDS STREAM] Stream cleanup completed for request {request_id}")


@router.get("/internals")
async def get_internals(request: Request, user=Depends(get_verified_user)):
    """Get agent internals for debugging and visualization"""
    agent = initialize_agent()
    if agent is None:
        raise HTTPException(status_code=500, detail="Strands AI agent not available")
    
    internals = get_agent_internals()
    if internals is None:
        raise HTTPException(status_code=500, detail="Failed to get agent internals")
    
    return internals

@router.post("/chat/completions")
async def chat_completions(
    request: Request, 
    chat_request: ChatRequest, 
    user=Depends(get_verified_user)
):
    """Handle chat completions with Strands AI agent"""
    start_time = datetime.now()
    request_id = f"strands-{int(start_time.timestamp())}"
    
    log.info(f"[STRANDS CHAT] ═══════════════════════════════════════════════════")
    log.info(f"[STRANDS CHAT] New chat completion request: {request_id}")
    log.info(f"[STRANDS CHAT] - Model: {chat_request.model}")
    log.info(f"[STRANDS CHAT] - Messages: {len(chat_request.messages)}")
    log.info(f"[STRANDS CHAT] - Stream: {chat_request.stream}")
    log.info(f"[STRANDS CHAT] - Include internals: {chat_request.include_internals}")
    log.info(f"[STRANDS CHAT] - Max tokens: {chat_request.max_tokens}")
    log.info(f"[STRANDS CHAT] - Temperature: {chat_request.temperature}")
    log.info(f"[STRANDS CHAT] - User: {user.name if hasattr(user, 'name') else 'Unknown'}")
    
    # Reset execution tracking for this request
    reset_execution_tracking()
    log.info(f"[STRANDS CHAT] Reset execution tracking")
    
    # Get model configuration to extract system prompt from params
    model_id = chat_request.model
    model_info = Models.get_model_by_id(model_id)
    system_prompt = None
    
    if model_info:
        params = model_info.params.model_dump()
        if params:
            system_prompt = params.get("system", None)
            if system_prompt:
                log.info(f"[STRANDS CHAT] Using system prompt from model params (length: {len(system_prompt)})")
            else:
                log.info(f"[STRANDS CHAT] No system prompt in model params, using default")
    else:
        log.info(f"[STRANDS CHAT] No model info found, using default system prompt")
    
    # Initialize agent with custom system prompt if available
    agent = initialize_agent(system_prompt=system_prompt)
    if agent is None:
        log.error(f"[STRANDS CHAT] ✗ Agent initialization failed")
        raise HTTPException(status_code=500, detail="Strands AI agent not available")
    
    # Extract user question (last message) and full conversation context
    question = extract_user_question(chat_request.messages)
    if not question:
        log.warning(f"[STRANDS CHAT] No user content found in messages")
        return ChatResponse(
            id=request_id,
            created=int(start_time.timestamp()),
            model=chat_request.model,
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": "No user content found."},
                "finish_reason": "stop"
            }]
        )
    
    # Build full conversation context including history
    conversation_context = build_conversation_context(chat_request.messages)
    log.info(f"[STRANDS CHAT] User question (truncated): {question[:300]}{'...' if len(question) > 300 else ''}")
    log.info(f"[STRANDS CHAT] Total conversation messages: {len(chat_request.messages)}")
    log.info(f"[STRANDS CHAT] Conversation context length: {len(conversation_context)} characters")
    
    try:
        # Check if streaming is requested
        if chat_request.stream:
            log.info(f"[STRANDS CHAT] Using streaming mode")
            # Return streaming response
            return StreamingResponse(
                stream_strands_response(
                    agent, 
                    conversation_context,  # Pass full conversation context instead of just the question
                    request_id, 
                    chat_request.model, 
                    start_time,
                    chat_request.include_internals,
                    system_prompt
                ),
                media_type="text/event-stream"
            )
        
        # Non-streaming response
        log.info(f"[STRANDS CHAT] Using non-streaming mode")
        log.info(f"[STRANDS CHAT] Calling Strands agent...")
        
        # Call the Strands agent directly with output capture
        answer = capture_agent_output(agent, conversation_context)  # Pass full conversation context
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        log.info(f"[STRANDS CHAT] ✓ Agent completed in {processing_time:.2f}s")
        log.info(f"[STRANDS CHAT] Response length: {len(str(answer))} characters")
        
        # Log the final agent response content
        answer_text = str(answer)
        if len(answer_text) > 1000:
            log.info(f"[STRANDS CHAT] Final agent response (truncated): {answer_text[:1000]}...")
        else:
            log.info(f"[STRANDS CHAT] Final agent response: {answer_text}")
        
        # Prepare response with agent internals (including execution time)
        # Pass the system prompt that was actually used
        internals = get_agent_internals(system_prompt=system_prompt)
        
        # Add execution time to metrics
        if internals and internals.metrics:
            internals.metrics["execution_time"] = round(processing_time, 2)
            internals.metrics["total_tokens"] = len(question.split()) + len(str(answer).split())
        
        log.info(f"[STRANDS CHAT] Agent internals collected: {internals is not None}")
        if internals:
            log.info(f"[STRANDS CHAT] Execution summary:")
            log.info(f"[STRANDS CHAT] - Tool calls: {sum(_tool_call_counts.values())}")
            log.info(f"[STRANDS CHAT] - Thinking steps: {len(internals.chain_of_thought)}")
            log.info(f"[STRANDS CHAT] - Execution log entries: {len(internals.execution_log)}")
        
        # Convert internals to JSON-safe dict
        internals_dict = None
        if internals:
            internals_dict = json.loads(json.dumps(internals.model_dump(), default=str))
            log.info(f"[STRANDS CHAT] Internals serialized successfully")
            
            # Log final chain of thought summary
            chain_of_thought = internals_dict.get('chain_of_thought', [])
            if chain_of_thought:
                log.info(f"[STRANDS FINAL_CHAIN_OF_THOUGHT] Complete thinking process ({len(chain_of_thought)} steps):")
                for i, step in enumerate(chain_of_thought, 1):
                    step_desc = step.get('description', 'No description')
                    step_timestamp = step.get('timestamp', 'No timestamp')
                    log.info(f"[STRANDS FINAL_CHAIN_OF_THOUGHT] {i}. {step_desc} [{step_timestamp}]")
        
        response_data = {
            "id": request_id,
            "object": "chat.completion",
            "created": int(start_time.timestamp()),
            "model": chat_request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant", 
                    "content": str(answer),
                    "strands_internals": internals_dict
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(conversation_context.split()),
                "completion_tokens": len(str(answer).split()),
                "total_tokens": len(conversation_context.split()) + len(str(answer).split())
            },
            "strands_internals": internals_dict
        }
        
        log.info(f"[STRANDS CHAT] Response prepared:")
        log.info(f"[STRANDS CHAT] - Choices: {len(response_data.get('choices', []))}")
        log.info(f"[STRANDS CHAT] - Content length: {len(str(answer))} chars")
        log.info(f"[STRANDS CHAT] - Has strands_internals: {internals_dict is not None}")
        log.info(f"[STRANDS CHAT] - Token usage: {response_data['usage']['total_tokens']}")
        log.info(f"[STRANDS CHAT] ✓ Request {request_id} completed successfully")
        log.info(f"[STRANDS CHAT] ═══════════════════════════════════════════════════")
        
        return response_data
        
    except Exception as e:
        log.error(f"[STRANDS CHAT] ✗ Error processing request {request_id}")
        log.error(f"[STRANDS CHAT] Error: {str(e)}")
        import traceback
        log.error(f"[STRANDS CHAT] Traceback: {traceback.format_exc()}")
        log.info(f"[STRANDS CHAT] ═══════════════════════════════════════════════════")
        
        return ChatResponse(
            id=request_id,
            created=int(start_time.timestamp()),
            model=chat_request.model,
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": f"Error processing request: {str(e)}"},
                "finish_reason": "stop"
            }]
        )

@router.get("/health")
async def health_check(request: Request, user=Depends(get_verified_user)):
    """Health check for Strands AI integration"""
    try:
        # Test agent initialization
        agent = initialize_agent()
        agent_status = "ok" if agent is not None else "error"
        
        # Test ClickHouse connectivity
        clickhouse_status = "unknown"
        if _clickhouse_client:
            try:
                databases = _clickhouse_client.list_databases()
                clickhouse_status = "ok" if "error" not in databases else "error"
            except Exception as e:
                clickhouse_status = "error"
                log.error(f"ClickHouse health check failed: {e}")
        
        return {
            "status": "ok" if agent_status == "ok" and clickhouse_status == "ok" else "degraded",
            "agent": agent_status,
            "clickhouse": clickhouse_status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        log.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }

@router.post("/tools/test")
async def test_tools(
    request: Request, 
    tool_request: Dict[str, Any], 
    user=Depends(get_verified_user)
):
    """Test individual tools for debugging"""
    agent = initialize_agent()
    if agent is None:
        raise HTTPException(status_code=500, detail="Strands AI agent not available")
    
    tool_name = tool_request.get("tool_name")
    tool_args = tool_request.get("args", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")
    
    try:
        if tool_name == "list_databases":
            result = _clickhouse_client.list_databases()
        elif tool_name == "list_tables":
            database = tool_args.get("database")
            if not database:
                raise HTTPException(status_code=400, detail="database parameter is required")
            result = _clickhouse_client.list_tables(
                database, 
                tool_args.get("like"), 
                tool_args.get("not_like")
            )
        elif tool_name == "run_select_query":
            query = tool_args.get("query")
            if not query:
                raise HTTPException(status_code=400, detail="query parameter is required")
            result = _clickhouse_client.run_select_query(query)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
        
        return {
            "tool_name": tool_name,
            "args": tool_args,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log.error(f"Tool test failed: {str(e)}")
        return {
            "tool_name": tool_name,
            "args": tool_args,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
