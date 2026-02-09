# ITASCA PFC MCP Integration Master Plan

## Executive Summary
This document outlines the comprehensive plan for integrating ITASCA Particle Flow Code (PFC) with the toyoura-nagisa MCP (Model Context Protocol) ecosystem. The integration will enable AI-powered control and analysis of PFC simulations through a sophisticated tool architecture, documentation system, and task management framework.

## 1. Architecture Overview

### 1.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         toyoura-nagisa                             │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐   ┌──────────────┐  │
│  │ Agent Profile│───▶│  MCP Server  │───▶│ Tool Manager │  │
│  │  (PFC Agent) │    │              │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                               │                              │
└───────────────────────────────┼─────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   PFC Bridge Server   │
                    │  (FastAPI + WebSocket)│
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │    PFC IPython SDK    │
                    │   (In-Software Shell) │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │      PFC Software      │
                    │    (Model & Engine)    │
                    └───────────────────────┘
```

### 1.2 Communication Flow
1. **User Request** → toyoura-nagisa Agent Profile
2. **Tool Selection** → MCP Server routes to appropriate PFC tools
3. **Command Translation** → PFC Bridge Server converts MCP calls to PFC commands
4. **Execution** → IPython SDK executes commands within PFC environment
5. **Response** → Results flow back through the chain to user

## 2. Agent Profile Design

### 2.1 PFC Specialist Agent Configuration

```python
{
    "id": "pfc-specialist",
    "name": "PFC Simulation Specialist",
    "description": "Expert in ITASCA PFC discrete element modeling and simulation",
    "capabilities": [
        "Create and modify PFC models",
        "Execute simulations and parametric studies",
        "Analyze particle mechanics and contacts",
        "Generate visualizations and reports",
        "Optimize model parameters"
    ],
    "tool_categories": [
        "coding",      # File I/O, bash commands
        "builtin",     # Web search for documentation
        "pfc",         # PFC-specific tools (new category)
        "analysis"     # Data analysis and visualization
    ],
    "context_injection": {
        "system_prompt": "pfc_specialist_prompt.md",
        "documentation_index": "pfc_docs_index",
        "example_library": "pfc_examples"
    }
}
```

### 2.2 Tool Categories Integration

#### Existing Tools (coding + builtin)
- **File Operations**: Read/Write/Edit PFC data files, scripts
- **Bash Commands**: System operations, file management
- **Grep/Glob/LS**: Search and navigate project structures
- **Web Search**: Search online PFC documentation and forums

#### New PFC Tools
- **pfc_execute**: Execute PFC commands directly
- **pfc_model_create**: Create new models with parameters
- **pfc_model_query**: Query model state and properties
- **pfc_simulation_run**: Run simulations with monitoring
- **pfc_data_extract**: Extract results and statistics
- **pfc_visualization**: Generate plots and animations

## 3. PFC Bridge Server Architecture

### 3.1 Server Design

```python
# backend/infrastructure/pfc/bridge_server.py

from fastapi import FastAPI, WebSocket
from typing import Dict, Any, Optional
import asyncio
import json

class PFCBridgeServer:
    """
    Bridge server connecting MCP tools to PFC IPython environment.
    
    Features:
    - WebSocket for real-time communication
    - Command queue management
    - Session persistence
    - Error handling and recovery
    - Performance monitoring
    """
    
    def __init__(self, pfc_kernel_path: str):
        self.app = FastAPI()
        self.pfc_kernel = None
        self.command_queue = asyncio.Queue()
        self.active_sessions: Dict[str, PFCSession] = {}
        
    async def connect_pfc_kernel(self):
        """Establish connection to PFC IPython kernel."""
        # Implementation details for kernel connection
        pass
        
    async def execute_command(self, command: str, session_id: str) -> Dict[str, Any]:
        """
        Execute PFC command in IPython environment.
        
        Returns:
        - result: Command output
        - status: Success/Error
        - metadata: Timing, memory usage, etc.
        """
        pass
        
    async def stream_results(self, websocket: WebSocket, session_id: str):
        """Stream simulation results in real-time."""
        pass
```

### 3.2 Communication Protocol

```json
{
    "request": {
        "id": "unique-request-id",
        "method": "pfc.execute",
        "params": {
            "command": "ball create radius 0.5 position 0 0 0",
            "session_id": "session-123",
            "timeout": 30000,
            "stream_output": true
        }
    },
    "response": {
        "id": "unique-request-id",
        "result": {
            "output": "Ball created with ID: 1",
            "status": "success",
            "execution_time": 0.023,
            "model_state": {
                "balls": 1,
                "walls": 0,
                "contacts": 0
            }
        }
    }
}
```

### 3.3 Session Management

```python
class PFCSession:
    """
    Manages individual PFC simulation sessions.
    
    Features:
    - Model state tracking
    - Command history
    - Checkpoint/restore
    - Resource management
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.model_state = {}
        self.command_history = []
        self.checkpoints = {}
        self.created_at = datetime.now()
        
    async def save_checkpoint(self, name: str):
        """Save current model state."""
        pass
        
    async def restore_checkpoint(self, name: str):
        """Restore model to previous state."""
        pass
```

## 4. Documentation and Knowledge System

### 4.1 Multi-Tier Documentation Strategy

```
┌─────────────────────────────────────────────┐
│          Documentation Layers                │
├─────────────────────────────────────────────┤
│ 1. Local Index (Fastest)                    │
│    - Command reference cache                 │
│    - Frequently used examples                │
│    - Validated code snippets                 │
├─────────────────────────────────────────────┤
│ 2. Vector Database (Semantic Search)        │
│    - PFC manual embeddings                   │
│    - Tutorial embeddings                     │
│    - Community solutions                     │
├─────────────────────────────────────────────┤
│ 3. Structured Database (Exact Match)        │
│    - Command syntax tables                   │
│    - Parameter specifications                │
│    - Error code mappings                     │
├─────────────────────────────────────────────┤
│ 4. Web Search (Fallback)                    │
│    - Latest documentation                    │
│    - Community forums                        │
│    - Research papers                         │
└─────────────────────────────────────────────┘
```

### 4.2 Documentation Index Implementation

```python
# backend/infrastructure/pfc/documentation/index.py

class PFCDocumentationIndex:
    """
    Hybrid documentation system for PFC knowledge.
    """
    
    def __init__(self):
        self.vector_db = ChromaDB(collection="pfc_docs")
        self.sql_db = SQLiteDB("pfc_commands.db")
        self.cache = RedisCache()
        
    async def search(self, query: str, context: Dict) -> List[Document]:
        """
        Multi-tier search strategy:
        1. Check cache for exact matches
        2. Vector similarity search
        3. SQL pattern matching
        4. Web search fallback
        """
        
        # Tier 1: Cache lookup
        cached = await self.cache.get(query)
        if cached:
            return cached
            
        # Tier 2: Vector search for semantic similarity
        vector_results = await self.vector_db.similarity_search(
            query=query,
            k=5,
            filter={"type": "pfc_command"}
        )
        
        # Tier 3: SQL for exact command syntax
        sql_results = await self.sql_db.query(
            f"SELECT * FROM commands WHERE name LIKE '%{query}%'"
        )
        
        # Tier 4: Web search if needed
        if not vector_results and not sql_results:
            web_results = await self.web_search(query)
            
        return self.merge_results(vector_results, sql_results, web_results)
```

### 4.3 Documentation Processing Pipeline

```python
# backend/infrastructure/pfc/documentation/processor.py

class PFCDocumentationProcessor:
    """
    Process and index PFC documentation.
    """
    
    async def process_manual(self, pdf_path: str):
        """Extract and index PFC manual."""
        # PDF parsing
        # Section extraction
        # Command identification
        # Example code extraction
        pass
        
    async def process_tutorials(self, tutorial_dir: str):
        """Process tutorial files."""
        # Code extraction
        # Explanation parsing
        # Dependency mapping
        pass
        
    async def validate_commands(self, commands: List[str]):
        """Validate commands against PFC version."""
        # Syntax checking
        # Version compatibility
        # Parameter validation
        pass
```

## 5. Enhanced TODO Tool System

### 5.1 Advanced TODO Tool Design

```python
# backend/infrastructure/mcp/tools/productivity/todo_advanced.py

@tool()
async def todo_create_plan(
    title: str,
    objectives: List[str],
    dependencies: Optional[Dict[str, List[str]]] = None,
    priority: Literal["high", "medium", "low"] = "medium"
) -> ToolResult:
    """
    Create a comprehensive task plan with dependencies.
    
    Features:
    - Hierarchical task structure
    - Dependency management
    - Priority assignment
    - Time estimation
    """
    pass

@tool()
async def todo_execute_task(
    task_id: str,
    action: Literal["start", "pause", "complete", "fail"],
    notes: Optional[str] = None,
    artifacts: Optional[List[str]] = None
) -> ToolResult:
    """
    Execute task state transitions with context.
    """
    pass

@tool()
async def todo_review_progress(
    plan_id: Optional[str] = None,
    include_metrics: bool = True
) -> ToolResult:
    """
    Review plan progress with analytics.
    
    Returns:
    - Completion percentage
    - Bottlenecks
    - Time estimates
    - Recommendations
    """
    pass

@tool()
async def todo_reflect(
    completed_tasks: List[str],
    learning_points: List[str],
    improvements: List[str]
) -> ToolResult:
    """
    Reflect on completed work for continuous improvement.
    """
    pass
```

### 5.2 ReAct Pattern Implementation

```python
class ReActAgent:
    """
    Reasoning + Acting pattern for PFC tasks.
    """
    
    async def reason(self, context: Dict) -> str:
        """Generate reasoning about current state."""
        # Analyze current situation
        # Identify goals
        # Consider constraints
        pass
        
    async def act(self, reasoning: str) -> Action:
        """Select and execute action based on reasoning."""
        # Tool selection
        # Parameter determination
        # Execution
        pass
        
    async def observe(self, action_result: Any) -> Observation:
        """Observe and interpret action results."""
        # Result analysis
        # Success/failure detection
        # Side effect identification
        pass
        
    async def reflect(self, observations: List[Observation]) -> Reflection:
        """Reflect on observations for learning."""
        # Pattern recognition
        # Strategy adjustment
        # Knowledge update
        pass
```

## 6. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up PFC Bridge Server basic structure
- [ ] Implement PFC IPython kernel connection
- [ ] Create basic command execution tool
- [ ] Set up development environment

### Phase 2: Core Tools (Week 3-4)
- [ ] Implement model creation tools
- [ ] Implement simulation control tools
- [ ] Implement data extraction tools
- [ ] Create agent profile configuration

### Phase 3: Documentation System (Week 5-6)
- [ ] Set up vector database for PFC docs
- [ ] Process PFC manual and tutorials
- [ ] Implement multi-tier search
- [ ] Create command validation system

### Phase 4: Advanced Features (Week 7-8)
- [ ] Implement session management
- [ ] Add checkpoint/restore functionality
- [ ] Create visualization tools
- [ ] Implement streaming results

### Phase 5: TODO Enhancement (Week 9)
- [ ] Implement advanced TODO tools
- [ ] Add ReAct pattern support
- [ ] Create progress analytics
- [ ] Add reflection capabilities

### Phase 6: Integration & Testing (Week 10-11)
- [ ] Full system integration testing
- [ ] Performance optimization
- [ ] Documentation completion
- [ ] Example library creation

### Phase 7: Deployment (Week 12)
- [ ] Production deployment setup
- [ ] Monitoring and logging
- [ ] User documentation
- [ ] Training materials

## 7. Technical Decisions

### 7.1 Database Selection

#### Vector Database (ChromaDB)
**Use for:**
- Semantic search of documentation
- Similar problem/solution matching
- Context retrieval

**Advantages:**
- Already integrated in toyoura-nagisa
- Excellent for natural language queries
- Supports metadata filtering

#### Structured Database (SQLite)
**Use for:**
- Command syntax reference
- Parameter specifications
- Exact match queries

**Advantages:**
- Fast exact lookups
- Relational data modeling
- ACID compliance

#### Hybrid Approach
```python
class HybridDocStore:
    def __init__(self):
        self.vector_store = ChromaDB()  # Semantic
        self.sql_store = SQLite()       # Structured
        self.cache = Redis()            # Hot data
        
    async def query(self, text: str, type: str = "auto"):
        if type == "command":
            return await self.sql_store.get_command(text)
        elif type == "concept":
            return await self.vector_store.search(text)
        else:
            # Intelligent routing based on query analysis
            return await self.smart_query(text)
```

### 7.2 Communication Architecture

**WebSocket + REST Hybrid**
- WebSocket for streaming simulations
- REST for command execution
- Message queue for reliability

**Protocol Selection: JSON-RPC 2.0**
- Standardized format
- Request/response correlation
- Error handling built-in

### 7.3 Security Considerations

```python
class SecurityLayer:
    """
    Security measures for PFC integration.
    """
    
    def validate_command(self, command: str) -> bool:
        """Validate PFC commands for safety."""
        # Prevent file system access outside workspace
        # Block dangerous system commands
        # Validate resource limits
        pass
        
    def sandbox_execution(self, command: str):
        """Execute in sandboxed environment."""
        # Resource limits
        # Timeout enforcement
        # Memory constraints
        pass
```

## 8. Testing Strategy

### 8.1 Unit Tests
```python
# tests/test_pfc_tools.py
class TestPFCTools:
    async def test_command_execution(self):
        """Test basic command execution."""
        pass
        
    async def test_model_creation(self):
        """Test model creation workflow."""
        pass
        
    async def test_error_handling(self):
        """Test error scenarios."""
        pass
```

### 8.2 Integration Tests
```python
# tests/test_pfc_integration.py
class TestPFCIntegration:
    async def test_end_to_end_workflow(self):
        """Test complete simulation workflow."""
        # Create model
        # Run simulation
        # Extract results
        # Verify outputs
        pass
```

### 8.3 Performance Tests
```python
# tests/test_pfc_performance.py
class TestPFCPerformance:
    async def test_command_latency(self):
        """Measure command execution latency."""
        pass
        
    async def test_streaming_throughput(self):
        """Test result streaming performance."""
        pass
```

## 9. Risk Mitigation

### 9.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| IPython kernel crashes | High | Implement auto-restart, session recovery |
| Documentation gaps | Medium | Multi-tier search, community resources |
| Performance bottlenecks | Medium | Caching, async processing, load balancing |
| Version incompatibility | Low | Version detection, compatibility layer |

### 9.2 Operational Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Resource exhaustion | High | Resource limits, monitoring, alerts |
| Data loss | High | Regular checkpoints, backup strategy |
| Security breaches | High | Sandboxing, input validation, audit logs |

## 10. Success Metrics

### 10.1 Performance KPIs
- Command execution latency < 500ms
- Documentation search accuracy > 90%
- Session recovery success rate > 95%
- Streaming throughput > 1000 msg/s

### 10.2 User Experience KPIs
- Task completion rate > 80%
- Error recovery rate > 90%
- Documentation helpfulness > 4/5
- Tool discovery rate > 70%

### 10.3 System Health KPIs
- Uptime > 99.9%
- Memory usage < 2GB
- CPU usage < 50% average
- Error rate < 1%

## 11. Future Enhancements

### 11.1 Short-term (3-6 months)
- Multi-model comparison tools
- Automated parameter optimization
- Result visualization dashboard
- Collaborative simulation features

### 11.2 Medium-term (6-12 months)
- AI-powered simulation suggestions
- Automatic report generation
- Cloud simulation deployment
- Mobile monitoring app

### 11.3 Long-term (12+ months)
- Multi-physics coupling (PFC + FLAC3D)
- Machine learning integration
- Virtual reality visualization
- Distributed computing support

## 12. Conclusion

This comprehensive plan provides a roadmap for integrating ITASCA PFC with the toyoura-nagisa MCP ecosystem. The architecture balances performance, reliability, and extensibility while providing a superior user experience for PFC simulation workflows.

Key success factors:
1. Robust communication architecture
2. Comprehensive documentation system
3. Intelligent tool design
4. Enhanced task management
5. Continuous improvement through ReAct

By following this plan, we will create a powerful AI-assisted PFC simulation environment that significantly enhances productivity and enables new possibilities in discrete element modeling.

## Appendix A: PFC Command Reference Structure

```sql
CREATE TABLE commands (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    syntax TEXT NOT NULL,
    description TEXT,
    parameters JSON,
    examples JSON,
    version TEXT,
    deprecated BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_command_name ON commands(name);
CREATE INDEX idx_command_category ON commands(category);
```

## Appendix B: Tool Registration Template

```python
# backend/infrastructure/mcp/tools/pfc/template.py

from mcp import tool
from typing import Dict, Any, Optional
from backend.domain.models.tool_result import ToolResult

@tool()
async def pfc_tool_name(
    required_param: str,
    optional_param: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Tool description following MCP standards.
    
    Args:
        required_param: Description
        optional_param: Description
        
    Returns:
        ToolResult with standardized structure
    """
    try:
        # Implementation
        result = await execute_pfc_command(...)
        
        return ToolResult(
            status="success",
            message="Human-readable summary",
            llm_content={"structured": "data"},
            data={"details": result}
        ).model_dump()
    except Exception as e:
        return ToolResult(
            status="error",
            message=f"Failed: {str(e)}",
            error=str(e)
        ).model_dump()
```

## Appendix C: Session State Schema

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional

class PFCSessionState(BaseModel):
    session_id: str
    created_at: datetime
    last_active: datetime
    model_state: Dict[str, Any]
    command_history: List[str]
    checkpoints: Dict[str, Any]
    resources: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None
    
class PFCModelState(BaseModel):
    balls: int
    walls: int
    contacts: int
    timestep: float
    time: float
    kinetic_energy: float
    strain_energy: float
    custom_data: Optional[Dict[str, Any]] = None
```

---

*Document Version: 1.0*
*Last Updated: 2025-01-07*
*Author: toyoura-nagisa Development Team*
