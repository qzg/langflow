# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common Development Commands

### Environment Setup
```bash
# Initial setup (installs dependencies and pre-commit hooks)
make init

# Check required tools are available
make check_tools

# Install backend dependencies only
make install_backend

# Install frontend dependencies only
make install_frontend
```

### Running the Application

```bash
# Quick start - build and run immediately
make run_cli

# Clean build and run (use when upgrading or build issues)
make run_clic

# Development mode - separate frontend/backend services
make backend    # Start FastAPI backend on :7860
make frontend   # Start Vite dev server on :3000

# Run with debug mode
make run_cli_debug
```

### Testing

```bash
# Unit tests (backend)
make unit_tests

# Unit tests with specific options
make unit_tests lf=true     # Last failed tests only
make unit_tests ff=true     # Failed first
make unit_tests async=false # Disable parallel execution

# LFX package tests
make lfx_tests

# Integration tests
make integration_tests
make integration_tests_no_api_keys  # Skip API key required tests
make integration_tests_api_keys     # Only API key required tests

# Frontend tests
make test_frontend                  # Jest unit tests
make test_frontend_coverage        # With coverage report  
make tests_frontend                 # Playwright e2e tests

# Template tests
make template_tests

# All tests
make tests
```

### Code Quality

```bash
# Format code
make format                # Both backend and frontend
make format_backend        # Backend only (ruff)
make format_frontend       # Frontend only (biome)

# Linting
make lint                  # MyPy type checking
make codespell            # Spell checking
make fix_codespell        # Fix spelling errors

# Unsafe formatting fixes
make unsafe_fix           # Apply unsafe ruff fixes
```

### Building and Packaging

```bash
# Build packages
make build base=true      # Build langflow-base only
make build main=true      # Build both langflow-base and langflow

# Build and install locally
make build_and_install

# Lock dependencies
make lock                 # Lock both base and main
make lock_base           # Lock base only
make lock_langflow       # Lock main only

# Update dependencies
make update
```

### Version Management

```bash
# Update version across all projects
make patch v=1.6.0
```

## High-Level Architecture

### Repository Structure

This is a **monorepo workspace** with three main packages:
- **langflow-base** (`src/backend/base/`) - Core Langflow engine and components
- **langflow** (root) - Main package with additional integrations and components  
- **lfx** (`src/lfx/`) - Command-line executor for running flows

### Backend Architecture

The backend is a **FastAPI application** with the following key layers:

**API Layer** (`src/backend/base/langflow/api/`)
- FastAPI routers organized by feature (flows, chat, auth, etc.)
- OpenAPI compatibility for LLM integration (`openai_responses.py`)
- MCP (Model Context Protocol) server support

**Core Engine** (`src/backend/base/langflow/`)
- **Graph system** - Processes node-based workflows with edges
- **Component system** - Extensible components for LLM providers, tools, data sources
- **Memory management** - Chat history and conversation state
- **Event system** - WebSocket support for real-time flow execution

**Database Layer**
- SQLAlchemy with Alembic migrations
- SQLite (default) with PostgreSQL support
- Models for flows, projects, folders, knowledge bases

### Frontend Architecture

**React + TypeScript** application (`src/frontend/`) using:
- **Vite** for build tooling and dev server
- **@xyflow/react** (ReactFlow) for visual flow editor
- **Tailwind CSS + Radix UI** for styling and components
- **Zustand** for state management
- **React Query** for API state management

The frontend provides:
- Visual drag-and-drop flow builder
- Component marketplace and custom component development
- Real-time chat interface with flows
- Project and folder management

### Key Integration Points

**Component System**: Both packages extend the same component base classes. Components can be:
- Python classes with specific interfaces
- Dynamically loaded from various locations
- Extended with custom tools and integrations

**Flow Execution**: Flows are JSON representations of directed graphs that get executed by the backend engine with support for:
- Parallel execution of independent nodes
- Memory and state management across conversations  
- Real-time streaming of results via WebSocket

**API Integration**: FastAPI backend serves both:
- RESTful API endpoints for flow management
- OpenAI-compatible endpoints for LLM integration
- WebSocket endpoints for real-time communication

## Development Notes

### Testing Strategy
- **Unit tests**: Focus on individual components and utilities
- **Integration tests**: Test API endpoints and flow execution
- **Frontend tests**: Jest for components, Playwright for e2e
- **Template tests**: Validate starter project functionality

### Key Technologies
- **Backend**: FastAPI, SQLAlchemy, LangChain, Pydantic, Alembic
- **Frontend**: React, TypeScript, ReactFlow, Tailwind, Radix UI
- **Build**: uv (Python), npm (Node.js), Docker
- **Testing**: pytest, Jest, Playwright
- **Code Quality**: ruff, mypy, biome, pre-commit

### Development Environment Requirements
- **Python 3.10-3.13** with **uv** package manager
- **Node.js v22.12 LTS** with **npm v10.9**
- **make** for build coordination
- **Docker** (optional, for containerized deployment)

### Common Workflows
1. **Adding components**: Add to appropriate subdirectory and update `__init__.py`
2. **Frontend development**: Use `make frontend` for hot-reload dev server
3. **API development**: Use `make backend` for FastAPI auto-reload
4. **Testing changes**: Run relevant test suites before committing
5. **Version updates**: Use `make patch v=X.Y.Z` for coordinated version bumps

### Database Migrations
```bash
# Create new migration
make alembic-revision message="Description"

# Apply migrations
make alembic-upgrade

# Check migration status  
make alembic-check
```

### Docker Development
```bash
# Build Docker images
make docker_build

# Development environment with Docker Compose
make docker_compose_up
```