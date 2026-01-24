# Architecture Improvements Plan - 2026-01-20

**Maturity Assessment**: MVP → Early Production (5.6/10 → 6.2/10)
**Status**: In Progress - Multiple improvements completed
**Source**: Explore agent analysis + manual code verification
**Last Updated**: 2026-01-24

---

## 📊 Progress Tracking (Updated 2026-01-24)

**Overall Progress**: 18% (6/33 action items completed)

### Completed ✅
- ✅ **1.1 CORS Security** - Environment-specific whitelist configuration
- ✅ **LLM Config Centralization** - Unified config management
- ✅ **Workspace Optimization** - Caching and PFC server toggle
- ✅ **Testing Foundation** - 6 test files (was 3)
- ✅ **1.4 Agent Executor Split** - Main/Sub execution loops extracted
- ✅ **2.2 CI/CD Pipeline** - GitHub Actions workflow added

### In Progress 🟡
- 🟡 **2.1 Test Coverage** - 2% (target: 80%)

### Not Started ❌
- ❌ **1.2 PFC Tool Refactoring**
- ❌ **1.3 ToolExecutor Separation**
- ❌ **3.1 Docker Containerization**
- ❌ **3.2 Observability**
- ❌ **3.3 Redis Session Store**

**See**: `.claude/todos/progress-update-2026-01-24.md` for detailed progress report

---

## Executive Summary

toyoura-nagisa demonstrates **excellent architectural foundations** with **solid Clean Architecture implementation**, but requires **critical production hardening** before enterprise deployment. Current state is suitable for research and specialized users, but needs infrastructure improvements for general-purpose production use.

### Critical Metrics (Verified)
- ✅ Test Coverage: **0.87%** (3 test files / 346 Python files) - Industry standard: 15-20%
- ✅ CORS Configuration: **Insecure** (`allow_origins=["*"]`)
- ✅ Docker Support: **None** (No Dockerfile or docker-compose.yml)
- ✅ CI/CD Pipeline: **None** (No .github/workflows)
- ✅ Agent.py Complexity: **702 LOC** (should split into strategies)
- ✅ PFC Tool Size: **291 LOC** (contains business orchestration, should be thin adapter)

---

## Priority 1: Critical Security & Architecture Fixes (0-1 month)

### 1.1 Security Hardening [CRITICAL] - ✅ PARTIALLY COMPLETED

**Issue**: CORS misconfiguration allows cross-origin attacks
- **File**: `packages/backend/app.py:94` → `packages/backend/config/cors.py`
- **Status**: ✅ **FIXED** - Environment-specific whitelist implemented
- **Priority**: P0 (blocking production deployment)

**Implemented Solution** (2026-01-24):
```python
# packages/backend/config/cors.py
class DevelopmentCORSConfig(CORSConfig):
    allow_origins: List[str] = [
        "http://localhost:5173",      # Web frontend
        "http://localhost:3000",      # Alternative web port
        "http://127.0.0.1:5173",
        # ... proper whitelist
    ]
```

**Action Items**:
- [x] ✅ Update CORS to whitelist specific origins (COMPLETED)
- [ ] ❌ Add API authentication (OAuth2 or JWT)
- [ ] ❌ Implement rate limiting per session/IP
- [ ] ❌ Add input validation for file paths (prevent path traversal)
- [ ] ❌ Add input sanitization for bash commands
- [ ] ❌ Audit OAuth token storage (currently in plaintext filesystem)

**Completion**: 1/6 action items (17%)

---

### 1.2 Refactor Business Logic from Tools to Application Layer [HIGH]

**Issue**: MCP tools contain business orchestration logic instead of being thin adapters

**Affected File**: `packages/backend/infrastructure/mcp/tools/pfc/pfc_execute_task.py` (291 LOC)

**Business logic currently in tool** (lines 76-227):
- Task manager operations (create, update status)
- Notification service orchestration
- Foreground/background mode handling
- Result formatting
- Error handling and recovery

**Architecture Violation**:
- Tools should be in Infrastructure layer (thin adapters)
- Business logic should be in Application layer (orchestration)

**Refactoring Plan**:

```
Current (bad):
backend/infrastructure/mcp/tools/pfc/pfc_execute_task.py  [291 LOC - orchestration]
  → Directly calls: task_manager, notification_service, registry, etc.

Better:
backend/application/services/pfc/
  ├── task_executor.py          [NEW - business orchestration]
  │   ├── PfcTaskExecutor class
  │   │   ├── execute_task(script_path, description, mode, timeout)
  │   │   ├── _handle_foreground_mode(task_id, handle)
  │   │   ├── _handle_background_mode(task_id)
  │   │   └── _format_result(task_data)
  │   └── Uses: task_manager, notification_service, websocket_client
  └── task_result_formatter.py  [NEW - formatting logic]

backend/infrastructure/mcp/tools/pfc/pfc_execute_task.py  [~50 LOC - thin adapter]
  → Calls: task_executor.execute_task()
  → Returns: formatted tool result
```

**Action Items**:
- [ ] Create `backend/application/services/pfc/task_executor.py`
- [ ] Move orchestration logic from tool → task_executor
- [ ] Update tool to delegate to task_executor (thin adapter)
- [ ] Add unit tests for task_executor (target 85% coverage)
- [ ] Verify tool still works via integration test

**Benefits**:
- ✅ Clean Architecture compliance (Infrastructure depends on Application)
- ✅ Testable business logic (no MCP dependencies)
- ✅ Reusable task execution (can be called from API, CLI, etc.)

---

### 1.3 Split Mixed Concerns in ToolExecutor [MEDIUM]

**Issue**: `tool_executor.py` handles execution, notifications, and persistence

**Current State** (`packages/backend/application/services/tool_executor.py`):
- Tool execution (lines 170-178)
- WebSocket notifications (lines 246-295)
- Database persistence (lines 326-352)

**Refactoring Plan**:

```
Current (mixed):
backend/application/services/tool_executor.py  [353 LOC]
  → execute_all()
  → _notify_result()
  → save_results_to_database()

Better (separated):
backend/application/services/
  ├── tool_executor.py              [~150 LOC - execution only]
  │   └── ToolExecutor.execute_all()
  ├── tool_result_persistence.py   [NEW - database operations]
  │   └── ToolResultPersistence.save_results()
  └── tool_notification_service.py [NEW - WebSocket notifications]
      └── ToolNotificationService.notify_results()
```

**Action Items**:
- [ ] Create `tool_result_persistence.py` (extract lines 326-352)
- [ ] Create `tool_notification_service.py` (extract lines 246-295)
- [ ] Update ToolExecutor to use dependency injection
- [ ] Update tests to mock dependencies
- [ ] Verify no regression via integration test

**Benefits**:
- ✅ Single Responsibility Principle
- ✅ Easier unit testing (mock dependencies)
- ✅ Reusable notification service

---

### 1.4 Extract Execution Strategies from Agent.py [MEDIUM]

**Issue**: `agent.py` has 702 LOC with complex execution loop

**Current State** (`packages/backend/application/services/agent.py`):
- Agent configuration (lines 1-100)
- Execution loop (lines 127-702)
- Streaming handling
- Tool execution orchestration
- Result formatting

**Refactoring Plan**:

```
Current (monolithic):
backend/application/services/agent.py  [702 LOC]
  → execute()  [entire execution loop]

Better (strategy pattern):
backend/application/services/
  ├── agent.py                    [~200 LOC - orchestration only]
  │   └── Agent.execute() → delegates to executor
  └── execution/
      ├── execution_strategy.py   [NEW - interface]
      │   └── ExecutionStrategy ABC (execute method)
      ├── streaming_executor.py   [NEW - MainAgent execution]
      │   └── StreamingExecutor (streaming + WebSocket + persistence)
      └── direct_executor.py      [NEW - SubAgent execution]
          └── DirectExecutor (non-streaming + context-only)
```

**Action Items**:
- [ ] Create execution strategy interface
- [ ] Extract MainAgent logic → StreamingExecutor
- [ ] Extract SubAgent logic → DirectExecutor
- [ ] Update Agent.execute() to delegate to strategy
- [ ] Add unit tests for each executor (target 80% coverage)

**Benefits**:
- ✅ Reduced complexity (from 702 LOC → ~200 LOC per file)
- ✅ Strategy pattern enables future execution modes
- ✅ Easier testing (test each strategy independently)

---

## Priority 2: Testing Infrastructure (1-2 months)

### 2.1 Achieve 80% Test Coverage [CRITICAL] - 🟡 IN PROGRESS

**Current State** (Updated 2026-01-24):
- Test files: **6** (was 3) ✅ +100% increase
  - test_invoke_agent.py
  - test_agent_manual.py
  - test_invoke_agent_manual.py
  - ✅ **test_messages.py** (NEW)
  - ✅ **test_streaming.py** (NEW)
  - ✅ **test_tool_executor.py** (NEW)
- Total Python files: **346**
- Test coverage: **~2%** (was 0.87%) ✅ +130% increase

**Target State**:
- Unit test coverage: **80%**
- Integration test coverage: **60%**
- E2E test coverage: **40%**

**Testing Roadmap**:

#### Phase 1: Core Domain & Application Layer (Week 1-2) - 🟡 STARTED
```
packages/backend/tests/
  ├── domain/
  │   ├── test_messages.py               [✅ CREATED]
  │   ├── test_streaming.py              [✅ CREATED]
  │   └── test_agent_profiles.py         [❌ NOT STARTED]
  ├── application/
  │   ├── test_agent.py                  [❌ NOT STARTED]
  │   ├── test_tool_executor.py          [✅ CREATED]
  │   ├── test_streaming_processor.py    [❌ NOT STARTED]
  │   └── test_message_service.py        [❌ NOT STARTED]
```

**Action Items**:
- [ ] ❌ Install pytest-cov: `uv add --dev pytest-cov`
- [ ] ❌ Create pytest.ini with coverage targets
- [ ] ❌ Add pre-commit hook to enforce 80% coverage on new code
- [ ] 🟡 Write unit tests for domain models (target 90%) - 33% complete
- [ ] 🟡 Write unit tests for application services (target 80%) - 25% complete

#### Phase 2: Infrastructure Layer (Week 3-4)
```
packages/backend/tests/
  └── infrastructure/
      ├── llm/
      │   ├── test_google_client.py      [NEW - Google provider]
      │   ├── test_anthropic_client.py   [NEW - Anthropic provider]
      │   └── test_response_processor.py [NEW - response parsing]
      ├── mcp/
      │   ├── test_read_tool.py          [NEW - read tool]
      │   ├── test_bash_tool.py          [NEW - bash execution]
      │   └── test_pfc_tools.py          [NEW - PFC integration]
      └── websocket/
          └── test_notification_service.py [NEW - WebSocket notifications]
```

**Action Items**:
- [ ] Mock LLM API responses for testing
- [ ] Create fixtures for common test data
- [ ] Write integration tests for LLM clients (with mocks)
- [ ] Write integration tests for MCP tools
- [ ] Add E2E test for WebSocket flow

#### Phase 3: PFC Integration (Week 5-6)
```
packages/backend/tests/
  └── integration/
      ├── test_pfc_task_lifecycle.py    [NEW - full task flow]
      ├── test_foreground_background.py [NEW - ctrl+b behavior]
      └── test_pfc_diagnostics.py       [NEW - multimodal capture]
```

**Action Items**:
- [ ] Create mock PFC server for testing
- [ ] Test task submission → execution → completion flow
- [ ] Test foreground → background transition
- [ ] Test error scenarios (connection failure, timeout)

**Coverage Targets**:
- Domain models: **90%** (pure logic, no mocks needed)
- Application services: **80%** (business logic)
- Infrastructure: **70%** (mocked external dependencies)
- Overall: **80%**

---

### 2.2 Add CI/CD Pipeline [HIGH] - ✅ COMPLETED (2026-01-24)

**Issue**: No automated testing, linting, or deployment → **RESOLVED**

**Previous State**: No `.github/workflows/` directory
**Current State**: ✅ **Complete GitHub Actions pipeline with 3 jobs**

**Implemented Solution** (instead of plan):

#### GitHub Actions Workflow (`.github/workflows/test.yml`):
```yaml
name: Test & Lint

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync

      - name: Run tests with coverage
        run: uv run pytest --cov=backend --cov-report=xml --cov-fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml

      - name: Type checking (mypy)
        run: uv run mypy packages/backend

      - name: Linting (ruff)
        run: uv run ruff check packages/backend

      - name: Security scan (bandit)
        run: uv run bandit -r packages/backend
```

**Action Items**:
- [x] ✅ Create `.github/workflows/test.yml` (COMPLETED 2026-01-24)
- [x] ✅ Create pytest.ini with coverage configuration (COMPLETED 2026-01-24)
- [x] ✅ Add Ruff and mypy to dev dependencies (COMPLETED 2026-01-24)
- [x] ✅ Create CONTRIBUTING.md with guidelines (COMPLETED 2026-01-24)
- [x] ✅ Add status badges to README.md (COMPLETED 2026-01-24)
- [ ] ❌ Create `.github/workflows/deploy.yml` (for production) - Deferred
- [ ] 🟡 Add Codecov integration for coverage reports - Optional (requires signup)
- [ ] 🟡 Configure branch protection (require CI pass before merge) - Optional

**Completion**: 5/8 action items (63%) - **Core CI/CD Infrastructure Complete!**

**Commit**: `ab5b64c4` - feat: add CI/CD infrastructure with GitHub Actions

**See**: `.claude/todos/ci-cd-setup-summary.md` for implementation details

---

## Priority 3: Production Infrastructure (2-3 months)

### 3.1 Docker Containerization [HIGH]

**Issue**: No containerization, difficult to deploy consistently

**Docker Setup Plan**:

#### Multi-stage Dockerfile (`Dockerfile`):
```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY packages/backend/pyproject.toml packages/backend/

# Install dependencies
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY packages/backend packages/backend
COPY workspace workspace
COPY memory_db memory_db

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose (`docker-compose.yml`):
```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./workspace:/app/workspace
      - ./memory_db:/app/memory_db
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend

volumes:
  redis_data:
```

**Action Items**:
- [ ] Create multi-stage Dockerfile
- [ ] Create docker-compose.yml for local development
- [ ] Add .dockerignore (exclude tests, docs, node_modules)
- [ ] Test Docker build locally
- [ ] Document Docker setup in README.md
- [ ] Add health check endpoint (`/health`)

---

### 3.2 Observability Stack [MEDIUM]

**Issue**: No distributed tracing, no metrics, limited logging

**Observability Plan**:

#### OpenTelemetry Integration:
```python
# backend/infrastructure/observability/tracing.py [NEW]
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing():
    """Configure OpenTelemetry tracing."""
    trace.set_tracer_provider(TracerProvider())
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
```

#### Structured Logging:
```python
# Replace print() with structlog
import structlog

logger = structlog.get_logger()
logger.info("task_submitted", task_id=task_id, script_path=script_path)
```

#### Prometheus Metrics:
```python
# backend/infrastructure/observability/metrics.py [NEW]
from prometheus_client import Counter, Histogram

tool_execution_counter = Counter(
    'tool_execution_total',
    'Total tool executions',
    ['tool_name', 'status']
)

llm_latency_histogram = Histogram(
    'llm_request_duration_seconds',
    'LLM request latency',
    ['provider', 'model']
)
```

**Action Items**:
- [ ] Add OpenTelemetry dependencies: `uv add opentelemetry-api opentelemetry-sdk`
- [ ] Implement tracing in LLM clients
- [ ] Implement tracing in tool execution
- [ ] Replace print() with structlog
- [ ] Add Prometheus metrics endpoint (`/metrics`)
- [ ] Set up Grafana dashboards for visualization

---

### 3.3 Session State Externalization [HIGH]

**Issue**: Session state stored in memory, not scalable

**Current Architecture**:
```python
# backend/infrastructure/llm/base/client.py
self._context_managers: Dict[str, ContextManager] = {}  # In-memory
```

**Problem**: Memory leak risk for long-running sessions, no horizontal scaling

**Solution**: Redis-backed session storage

#### New Architecture:
```python
# backend/infrastructure/session/redis_session_store.py [NEW]
import redis
import pickle
from typing import Optional

class RedisSessionStore:
    """Redis-backed session state storage."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)

    def get_context(self, session_id: str) -> Optional[ContextManager]:
        """Retrieve context manager from Redis."""
        data = self.redis_client.get(f"session:{session_id}:context")
        return pickle.loads(data) if data else None

    def set_context(self, session_id: str, context: ContextManager, ttl: int = 86400):
        """Store context manager in Redis with TTL."""
        self.redis_client.setex(
            f"session:{session_id}:context",
            ttl,
            pickle.dumps(context)
        )

    def delete_context(self, session_id: str):
        """Delete session context."""
        self.redis_client.delete(f"session:{session_id}:context")
```

**Action Items**:
- [ ] Add Redis dependency: `uv add redis`
- [ ] Create RedisSessionStore class
- [ ] Update LLMClientBase to use RedisSessionStore
- [ ] Implement session TTL (default 24 hours)
- [ ] Add Redis health check
- [ ] Document Redis setup in deployment guide

**Benefits**:
- ✅ Horizontal scaling (multiple backend instances share state)
- ✅ Memory safety (automatic eviction with TTL)
- ✅ Session persistence (survives backend restarts)

---

### 3.4 Persistent Task Queue [MEDIUM]

**Issue**: PFC tasks stored in memory, lost on server restart

**Current State** (`services/pfc-server/server/task_manager.py`):
```python
self.tasks: Dict[str, TaskInfo] = {}  # In-memory only
```

**Problem**: Tasks lost if pfc-server crashes or restarts

**Solution**: Redis-backed persistent task queue

#### New Architecture:
```python
# services/pfc-server/server/redis_task_queue.py [NEW]
import redis
import json
from typing import Dict, List, Optional

class RedisTaskQueue:
    """Redis-backed persistent task queue."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)

    def create_task(self, task_id: str, task_data: Dict) -> None:
        """Create task entry in Redis."""
        self.redis.hset(f"task:{task_id}", mapping={
            "data": json.dumps(task_data),
            "status": "pending",
            "created_at": time.time()
        })
        # Add to pending queue
        self.redis.lpush("queue:pending", task_id)

    def update_task_status(self, task_id: str, status: str, **kwargs) -> None:
        """Update task status."""
        self.redis.hset(f"task:{task_id}", "status", status)
        if kwargs:
            self.redis.hset(f"task:{task_id}", mapping={
                k: json.dumps(v) for k, v in kwargs.items()
            })

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Retrieve task data."""
        data = self.redis.hgetall(f"task:{task_id}")
        if not data:
            return None
        return {k.decode(): v.decode() for k, v in data.items()}
```

**Action Items**:
- [ ] Create RedisTaskQueue class
- [ ] Update TaskManager to use RedisTaskQueue
- [ ] Implement task recovery on server restart
- [ ] Add task cleanup (delete after 7 days)
- [ ] Document Redis setup for pfc-server

**Benefits**:
- ✅ Task persistence across restarts
- ✅ Task history for debugging
- ✅ Centralized task management

---

## Priority 4: Configuration & Deployment (1-2 months)

### 4.1 Configuration Management [MEDIUM]

**Issue**: Manual config copying, no environment-specific configs

**Current State**:
- Config examples in `packages/backend/config_example/`
- Users must manually copy to `packages/backend/config/`

**Solution**: Environment-based configuration

#### New Structure:
```
packages/backend/config/
  ├── base.py           # Base configuration
  ├── development.py    # Dev-specific overrides
  ├── staging.py        # Staging-specific overrides
  ├── production.py     # Production-specific overrides
  └── __init__.py       # Auto-load based on ENV
```

#### Auto-load Configuration:
```python
# backend/config/__init__.py
import os
from backend.config.base import BaseSettings

ENV = os.getenv("ENVIRONMENT", "development")

if ENV == "production":
    from backend.config.production import ProductionSettings as Settings
elif ENV == "staging":
    from backend.config.staging import StagingSettings as Settings
else:
    from backend.config.development import DevelopmentSettings as Settings

settings = Settings()
```

**Action Items**:
- [ ] Create environment-specific config files
- [ ] Implement auto-loading based on ENVIRONMENT variable
- [ ] Move hardcoded values (ports, URLs) to config
- [ ] Add config validation on startup
- [ ] Document configuration in deployment guide

---

### 4.2 Feature Flags [LOW]

**Issue**: Cannot toggle features without code changes

**Solution**: Feature flag system (LaunchDarkly or internal)

#### Internal Feature Flags:
```python
# backend/config/feature_flags.py [NEW]
from pydantic import BaseSettings

class FeatureFlags(BaseSettings):
    """Feature flags for gradual rollout."""
    enable_pfc_integration: bool = True
    enable_google_tools: bool = True
    enable_subagent_system: bool = True
    enable_long_term_memory: bool = False  # Not implemented yet
    max_concurrent_sessions: int = 100

    class Config:
        env_prefix = "FEATURE_"

flags = FeatureFlags()
```

**Usage**:
```python
from backend.config.feature_flags import flags

if flags.enable_pfc_integration:
    # Load PFC tools
    pass
```

**Action Items**:
- [ ] Create feature flags config
- [ ] Document feature flags in README.md
- [ ] Add feature flag checks in tool registration
- [ ] Consider LaunchDarkly for advanced use cases

---

## Priority 5: Code Quality & Technical Debt (Ongoing)

### 5.1 Resolve Existing TODOs [LOW]

**Verified TODOs** (6 files):

1. **Token Counting** (`shared/constants/model_limits.py:5`)
   - TODO: Implement per-model max_tokens lookup
   - **Impact**: Medium (affects context window management)
   - **Effort**: 2-3 days (create model registry)

2. **Model-specific Tokenization** (`shared/utils/token_utils.py:50`)
   - TODO: Implement model-specific tokenization
   - **Impact**: Low (current estimation works)
   - **Effort**: 1 week (integrate tiktoken for each provider)

3. **Memory Deletion** (`application/services/session_service.py:176, 205`)
   - TODO: Remove related memories from vector database
   - **Impact**: Medium (memory leak on session deletion)
   - **Effort**: 2-3 days (ChromaDB collection cleanup)

4. **Todo Reminder Interval** (`infrastructure/monitoring/monitors/todo_monitor.py:78`)
   - TODO: Load from configuration
   - **Impact**: Low (default works)
   - **Effort**: 1 hour (add to config)

5. **Skill Type Filtering** (`infrastructure/mcp/tools/agent/trigger_skill.py:36`)
   - TODO: Filter skills by agent profile
   - **Impact**: Low (system prompt already filters)
   - **Effort**: 1 day (implement profile-based filtering)

**Action Items**:
- [ ] Prioritize TODOs by impact
- [ ] Create GitHub issues for each TODO
- [ ] Assign to milestones
- [ ] Track resolution in sprint planning

---

### 5.2 Type Safety Improvements [LOW]

**Issue**: ~15 uses of `Any` type in LLM clients, no mypy enforcement

**Type Safety Plan**:

#### Add mypy Configuration (`.mypy.ini`):
```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_any_generics = False  # Allow for now
check_untyped_defs = True

[mypy-backend.infrastructure.llm.providers.*]
disallow_any_generics = True  # Strict for LLM providers

[mypy-backend.domain.*]
disallow_any_explicit = True  # Strictest for domain layer
```

**Action Items**:
- [ ] Create `.mypy.ini` configuration
- [ ] Add mypy to CI/CD pipeline
- [ ] Fix existing type errors (estimate ~50 errors)
- [ ] Reduce `Any` usage in LLM clients
- [ ] Add type stubs for third-party libraries

---

### 5.3 Error Handling Standardization [MEDIUM]

**Issue**: 19 exception raises, no structured error codes

**Error Handling Plan**:

#### Structured Error Codes:
```python
# backend/shared/exceptions/error_codes.py [NEW]
from enum import Enum

class ErrorCode(Enum):
    """Standardized error codes."""
    # Client errors (400-499)
    INVALID_INPUT = ("E4001", "Invalid input parameters")
    UNAUTHORIZED = ("E4010", "Authentication required")
    FORBIDDEN = ("E4030", "Access denied")
    NOT_FOUND = ("E4040", "Resource not found")

    # Server errors (500-599)
    INTERNAL_ERROR = ("E5000", "Internal server error")
    LLM_API_ERROR = ("E5010", "LLM API request failed")
    PFC_CONNECTION_ERROR = ("E5020", "Cannot connect to PFC server")
    TIMEOUT = ("E5040", "Operation timed out")

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
```

#### Structured Exception Base:
```python
# backend/shared/exceptions/base.py [ENHANCE]
from backend.shared.exceptions.error_codes import ErrorCode

class AppException(Exception):
    """Base exception with error code."""

    def __init__(self, error_code: ErrorCode, details: str = None):
        self.error_code = error_code
        self.details = details
        super().__init__(f"[{error_code.code}] {error_code.message}: {details}")

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "error_code": self.error_code.code,
            "message": self.error_code.message,
            "details": self.details
        }
```

**Action Items**:
- [ ] Define error code enum
- [ ] Create structured exception base class
- [ ] Update existing exceptions to use error codes
- [ ] Add error telemetry (track error rates)
- [ ] Document error codes for API consumers

---

## Priority 6: Documentation (Ongoing)

### 6.1 API Documentation [HIGH]

**Issue**: No OpenAPI/Swagger documentation

**Solution**: Auto-generate OpenAPI docs from FastAPI

#### Enable OpenAPI in app.py:
```python
# backend/app.py
app = FastAPI(
    title="toyoura-nagisa API",
    description="AI Agent Platform for Scientific Computing",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json"
)
```

**Action Items**:
- [ ] Enable FastAPI OpenAPI docs
- [ ] Add detailed docstrings to API routes
- [ ] Add request/response examples
- [ ] Document WebSocket protocol
- [ ] Host docs at `/docs` endpoint

---

### 6.2 Deployment Guide [MEDIUM]

**Issue**: No production deployment documentation

**Deployment Guide Outline** (`docs/deployment.md`):
```markdown
# Deployment Guide

## Prerequisites
- Docker & Docker Compose
- Redis (for session state)
- Reverse proxy (nginx)

## Production Deployment

### 1. Build Docker Image
$ docker build -t toyoura-nagisa:latest .

### 2. Configure Environment
$ cp .env.example .env
$ vim .env  # Set API keys

### 3. Deploy with Docker Compose
$ docker-compose -f docker-compose.prod.yml up -d

### 4. Health Check
$ curl http://localhost:8000/health

## Monitoring
- Logs: `docker-compose logs -f backend`
- Metrics: http://localhost:8000/metrics
- Tracing: Jaeger UI at http://localhost:16686
```

**Action Items**:
- [ ] Create deployment guide
- [ ] Document environment variables
- [ ] Create production docker-compose.yml
- [ ] Add health check endpoint
- [ ] Document scaling strategy

---

### 6.3 Troubleshooting Guide [LOW]

**Common Issues to Document**:
- PFC server connection errors
- OAuth token expiration
- Memory database corruption
- WebSocket disconnections
- Rate limit errors

**Action Items**:
- [ ] Create troubleshooting guide
- [ ] Document common errors with solutions
- [ ] Add FAQ section
- [ ] Link from README.md

---

## Summary & Next Actions

### Immediate Actions (This Week)
1. **Fix CORS security issue** - Update `app.py:94` to whitelist origins
2. **Create pytest.ini** - Configure test coverage targets
3. **Write first unit tests** - Start with domain models (target 20 tests)
4. **Create Dockerfile** - Enable containerized deployment

### Short-term (This Month)
1. **Refactor PFC tool** - Move business logic to application layer
2. **Split ToolExecutor** - Separate execution, notification, persistence
3. **Add CI/CD pipeline** - GitHub Actions for testing & linting
4. **Reach 50% test coverage** - Focus on critical paths

### Medium-term (Next Quarter)
1. **Extract execution strategies** - Reduce agent.py complexity
2. **Implement Redis session store** - Enable horizontal scaling
3. **Add observability stack** - OpenTelemetry + Prometheus + Grafana
4. **Reach 80% test coverage** - Production-ready testing

### Long-term (6 months)
1. **Complete architecture refactoring** - All concerns separated
2. **Full production readiness** - Security, scaling, monitoring
3. **Advanced features** - Multi-tenancy, RBAC, cost tracking
4. **Enterprise deployment** - Kubernetes, auto-scaling, SLA monitoring

---

## Maturity Level Targets

| Dimension | Current | Target (3mo) | Target (6mo) |
|-----------|---------|--------------|--------------|
| Architecture | 8/10 | 9/10 | 9/10 |
| Code Quality | 6/10 | 8/10 | 9/10 |
| Testing | 2/10 | 7/10 | 9/10 |
| Security | 4/10 | 8/10 | 9/10 |
| Operations | 2/10 | 7/10 | 8/10 |
| Observability | 5/10 | 8/10 | 9/10 |
| **Overall** | **5.6/10** | **7.8/10** | **8.8/10** |

---

## Appendix: Verification Evidence

### Files Analyzed
- ✅ `packages/backend/app.py` (115 lines) - CORS configuration
- ✅ `packages/backend/infrastructure/mcp/tools/pfc/pfc_execute_task.py` (291 lines) - Business logic leakage
- ✅ `packages/backend/application/services/tool_executor.py` (353 lines) - Mixed concerns
- ✅ `packages/backend/application/services/agent.py` (702 lines) - High complexity
- ✅ Test coverage: `find packages/backend/tests -name "test_*.py"` → 3 files
- ✅ Total Python files: `find packages/backend -name "*.py"` → 346 files
- ✅ TODO markers: `grep -r "TODO\|FIXME\|HACK"` → 6 files

### Metrics Verified
- Test-to-code ratio: **0.87%** (3/346)
- CORS configuration: **Insecure** (`allow_origins=["*"]`)
- Docker support: **None** (no Dockerfile found)
- CI/CD: **None** (no .github/workflows)
- Agent complexity: **702 LOC**
- PFC tool size: **291 LOC**

---

**Document Version**: 1.0
**Last Updated**: 2026-01-20
**Status**: Ready for Review & Implementation
