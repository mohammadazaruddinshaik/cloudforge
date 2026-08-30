# CloudForge

**Cloud Deployment Orchestration Engine**

CloudForge is a platform designed to reduce the infrastructure burden on developers by analyzing application repositories and progressively orchestrating their deployment to AWS.

The goal is simple:

> **Developers focus on building applications. CloudForge handles the analysis, planning, containerization, and deployment workflow.**

## Project Vision

CloudForge takes a full-stack application repository and progressively transforms it into a validated, deployable cloud application:

```text
Application Repository
        ↓
Phase 1: Repository Analysis
        ↓
Phase 2: Deployment Planning
        ↓
Phase 3.1: Containerization Planning
        ↓
Phase 3.2: Dockerfile Generation
        ↓
Phase 3.3: Docker Build & Runtime Validation
        ↓
Phase 4: AWS Deployment (ECR/ECS)
```

The deployment workflow uses explicit checkpoints and validation rather than blindly deploying generated infrastructure.

---

# Implementation Status

## Phase 1 — Repository Analysis ✅ COMPLETE

Phase 1 understands what the developer has built.

CloudForge analyzes repositories by:

* Discovering relevant repository files
* Detecting application services
* Parsing supported project manifests (package.json, pyproject.toml, requirements.txt, etc.)
* Normalizing dependencies
* Detecting languages, runtimes, and frameworks
* Identifying likely application entry points
* Detecting application ports from evidence
* Identifying environment variables safely (without exposing secrets)
* Analyzing existing Docker configuration
* Detecting external dependencies
* Building evidence-based service relationships
* Attaching confidence scores and evidence to inferences
* Handling unknown and ambiguous repositories conservatively

**Current support:** Representative Node.js and Python repository patterns. Analysis is intentionally evidence-driven rather than claiming universal ecosystem support.

**Validated against:**
* MERN applications
* Python/FastAPI applications
* Multi-manifest Python services
* Next.js applications
* Multi-service repositories
* Unknown/unsupported repositories
* Malformed manifests
* Different environment-variable naming conventions

---

## Phase 2 — Deployment Planning ✅ COMPLETE

Phase 2 converts repository analysis into an **evidence-backed deployment plan**.

It answers: **"Given what the developer built, how should it be deployed?"**

CloudForge determines:

* Services requiring deployment
* Deployment type and strategy
* Runtime and framework
* Dependency installation command
* Build command (when applicable)
* Start command
* Production serving strategy (when detectable from evidence)
* Application ports (when known)
* Required environment variables
* External dependencies
* Service relationships
* Container requirements
* AWS ECR/ECS target
* Assumptions, warnings, and blockers
* Deployment readiness state

**Readiness States:**
```text
🟢 ready                    — Sufficient evidence; safe to proceed
🟡 requires_confirmation    — Incomplete evidence; manual review needed
🔴 blocked                  — Fatal issues; cannot proceed safely
```

CloudForge does not treat unknown information as ready-to-deploy. For example, if a frontend's production serving strategy or port cannot be determined, it reports `requires_confirmation` rather than silently guessing.

**Phase 2 Scope:**
Phase 2 is planning-only. It does **not**:
* Generate Dockerfiles
* Build Docker images
* Execute Docker
* Create ECR repositories
* Create ECS services
* Provision AWS infrastructure
* Call AWS APIs

---

## Phase 3.1 — Containerization Planning ✅ COMPLETE

Phase 3.1 converts the deployment plan into a containerization plan.

CloudForge:

* Determines container requirements from the deployment plan
* Preserves runtime, build, and start commands
* Determines build context
* Preserves environment requirements
* Maintains readiness and uncertainty states from Phase 2
* Does not invent runtime versions, ports, or production serving strategies

Output: A structured containerization plan ready for Dockerfile generation.

---

## Phase 3.2 — Dockerfile Generation ✅ COMPLETE

Phase 3.2 deterministically generates Dockerfile content from the containerization plan.

CloudForge:

* Generates Dockerfile content from containerization plan
* Separates dependency installation from build steps
* Respects working directory and build context
* Exposes ports only when known
* Preserves unresolved serving strategies as comments or labels
* Never embeds secrets in Dockerfiles
* Does not use LLM/agents to generate content

**Important:** Generated Dockerfiles are produced as structured output/content. This phase does not mean CloudForge has deployed anything.

---

## Phase 3.3 — Docker Build & Runtime Validation ✅ COMPLETE

Phase 3.3 validates generated Dockerfiles through build and runtime testing.

CloudForge implements:

* Docker CLI abstraction layer
* Docker image build validation
* Container runtime startup validation
* Build/runtime status separation
* Log capture and analysis
* Container cleanup (stop/remove)
* Docker-unavailable graceful handling
* Fake/injected Docker client testing (deterministic without real daemon)
* Readiness-aware validation (respects Phase 3.1 readiness states)
* Secret redaction in logs and output

**Important:** 
> Real Docker execution has not been validated in the current development environment because the Docker daemon was unavailable during testing. The implementation handles this condition gracefully and does not claim the MERN application was successfully built/run in Docker.

The Phase 3.3 test suite uses injected FakeDockerClient for deterministic coverage independent of Docker daemon availability.

---

# Architecture

## Phase Pipeline

```text
Repository
    ↓
[Phase 1: Repository Analysis]
    ↓ (analysis model)
[Phase 2: Deployment Planning]
    ↓ (deployment plan)
[Phase 3.1: Containerization Planning]
    ↓ (containerization plan)
[Phase 3.2: Dockerfile Generation]
    ↓ (dockerfile + content)
[Phase 3.3: Docker Build & Runtime Validation]
    ↓ (validation result)
[Phase 4: AWS Deployment] (planned)
```

## Source Structure

```text
app/
├── analysis/              (Phase 1: Repository analysis)
│   ├── repository.py
│   ├── detectors/
│   ├── parsers/
│   ├── discovery/
│   ├── docker/
│   ├── environment/
│   ├── external/
│   ├── relationships/
│   ├── services/
│   └── source/
├── planning/              (Phase 2: Deployment planning)
│   ├── planner.py
│   ├── models.py
│   └── validators.py
├── containerization/      (Phase 3: Containerization)
│   ├── planner.py
│   ├── dockerfile_generator.py
│   ├── docker_client.py
│   ├── docker_validator.py
│   └── models.py
├── api/                   (REST endpoints)
│   └── routes/
├── core/
│   ├── configuration.py
│   ├── exceptions.py
│   └── registry.py
└── main.py
```

---

# Example: MERN Fixture

CloudForge is tested against a representative MERN (MongoDB, Express, React, Node.js) application:

**Backend Service:**
```
Runtime:       Node.js
Framework:     Express
Entry Point:   server.js
Port:          5000 (detected from source)
Dependencies:  MongoDB (external)
Status:        Containerization Ready ✓
```

**Frontend Service:**
```
Runtime:       Node.js
Framework:     React
Entry Point:   src/App.js
Port:          Unknown (dev vs. production unclear)
Serving:       Production strategy unresolved
Status:        Requires Confirmation (needs port + serving strategy)
```

CloudForge intentionally marks the frontend as `requires_confirmation` rather than:
* Assuming Nginx as a proxy
* Inventing a port number
* Guessing a serving strategy

This conservative approach prevents silent misconfigurations that could fail in production.

---

# Reliability Principles

CloudForge follows these core principles:

### 1. Evidence-First Analysis
* Decisions are based on detected evidence, not assumptions
* Confidence scores and evidence chains are preserved
* Inferences are explicitly labeled as such

### 2. Conservative Unknown Handling
* Unknown information is not treated as "ready to deploy"
* Ambiguous cases report `requires_confirmation`
* Developers make final deployment decisions

### 3. Explicit Readiness States
```text
ready               → Sufficient evidence to proceed
requires_confirmation → Manual review needed
blocked             → Cannot proceed safely
```

### 4. No Secret Exposure
* Secrets are redacted during analysis
* Secrets are not embedded in generated Dockerfiles
* Secrets are redacted from logs and validation output

### 5. No Invented Infrastructure
* Ports are not guessed
* Runtime versions are not assumed
* Production serving strategies are not invented
* Service relationships are not speculated

### 6. Separation of Planning and Execution
* Planning phases produce structured plans, not deployments
* Validation is separate from execution
* Plans can be reviewed before execution

### 7. Validation Before Deployment
* Generated artifacts are validated before use
* Build validation is separate from runtime validation
* Cleanup is verified

---

# Testing

**Current Test Coverage:**
```
65 tests passing
1 non-blocking warning (FastAPI/Starlette httpx deprecation)
```

**Test Coverage by Phase:**
* Phase 1 — Repository Analysis: Parsing, detection, relationships
* Phase 2 — Deployment Planning: Planning logic, readiness determination
* Phase 3.1 — Containerization Planning: Containerization readiness
* Phase 3.2 — Dockerfile Generation: Dockerfile content generation
* Phase 3.3 — Docker Validation: Build validation, runtime validation, cleanup, secret redaction

Tests use:
* Fixtures for representative application structures
* Fake/injected Docker clients for deterministic validation
* No real Docker daemon requirement
* No AWS credentials or API calls

---

# Technology Stack

## Current

* **Language:** Python 3.12+
* **Web Framework:** FastAPI
* **Validation:** Pydantic
* **Testing:** Pytest
* **Container:** Docker CLI abstraction
* **Package Management:** Poetry (pyproject.toml)

## Planned

* **AWS Infrastructure:** Boto3, ECR, ECS
* **Orchestration:** LangGraph
* **Frontend:** React with WebSockets
* **Real-time Updates:** WebSocket integration

---

# Current Project Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Repository Analysis | ✅ COMPLETE |
| 2 | Deployment Planning | ✅ COMPLETE |
| 3.1 | Containerization Planning | ✅ COMPLETE |
| 3.2 | Dockerfile Generation | ✅ COMPLETE |
| 3.3 | Docker Build & Runtime Validation | ✅ COMPLETE |
| 4 | AWS Deployment (ECR/ECS) | ⏳ PLANNED |
| 5 | Agentic Orchestration | ⏳ PLANNED |
| 6 | Dashboard | ⏳ PLANNED |

**Clarification:** AWS/ECR/ECS deployment has NOT been implemented yet. Phase 4 will handle this in future work.

---

# Development Checkpoints

The project uses Git checkpoints between major phases:

```text
phase-1-complete
        ↓
phase-2-complete
        ↓
phase-3-complete
        ↓
phase-4-complete (planned)
```

This allows later development phases to build on a known-good foundation without destabilizing earlier functionality.
