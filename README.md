# CloudForge

**AI-Assisted Cloud Deployment Orchestration Engine**

CloudForge is a platform designed to reduce the infrastructure burden on developers by analyzing application repositories and progressively orchestrating their deployment to AWS.

The goal is simple:

> **Developers focus on building applications. CloudForge handles the infrastructure and deployment workflow.**

## Project Vision

CloudForge takes a full-stack application repository and progressively transforms it into a deployable cloud application:

```text
Application Repository
        ↓
Repository Analysis
        ↓
Deployment Planning
        ↓
Containerization
        ↓
Validation
        ↓
Amazon ECR
        ↓
Amazon ECS
```

The deployment workflow uses explicit checkpoints and validation rather than blindly deploying generated infrastructure.

---

# Current Status

## Phase 1 — Repository Analysis ✅

Phase 1 understands what the developer has built.

CloudForge currently:

* Discovers relevant repository files
* Detects application services
* Parses supported project manifests
* Normalizes dependencies
* Detects languages, runtimes, and frameworks
* Identifies likely application entry points
* Detects application ports
* Identifies environment variables without exposing secret values
* Analyzes existing Docker configuration
* Detects external dependencies
* Builds evidence-based service relationships
* Attaches confidence and evidence to important inferences
* Handles unknown and ambiguous repositories conservatively

Validated against representative:

* MERN applications
* Python/FastAPI applications
* Multi-manifest Python services
* Next.js applications
* Multi-service repositories
* Unknown/unsupported repositories
* Malformed manifests
* Different environment-variable naming conventions

**Status: Complete**

---

## Phase 2 — Deployment Planning ✅

Phase 2 converts the repository analysis into an **evidence-backed deployment plan**.

It answers:

> **"Given what the developer built, how should it be deployed?"**

The planner determines:

* Services that require deployment
* Deployment type
* Runtime and framework
* Dependency installation strategy
* Build strategy
* Start command
* Production serving strategy
* Application ports
* Required environment variables
* External dependencies
* Service relationships
* Networking requirements
* Container requirements
* AWS ECR/ECS target
* Assumptions
* Warnings
* Blockers
* Deployment readiness

The planner explicitly distinguishes:

```text
🟢 ready
🟡 requires_confirmation
🔴 blocked
```

CloudForge does not treat unknown information as ready-to-deploy information.

For example, if a frontend's production serving strategy or port cannot be reliably determined, CloudForge reports:

```text
deployment_readiness: requires_confirmation
deployment_ready: false
```

rather than silently guessing.

### Phase 2 Scope

Phase 2 is planning-only.

It does **not**:

* Generate Dockerfiles
* Build Docker images
* Execute Docker
* Create ECR repositories
* Create ECS services
* Provision AWS infrastructure
* Call AWS APIs
* Deploy applications

**Status: Complete**

---

# Architecture

The current architecture separates repository intelligence from deployment planning:

```text
                Repository
                    │
                    ▼
        ┌──────────────────────┐
        │ Phase 1              │
        │ Repository Analysis  │
        └──────────┬───────────┘
                   │
                   ▼
          Repository Model
                   │
                   ▼
        ┌──────────────────────┐
        │ Phase 2              │
        │ Deployment Planning  │
        └──────────┬───────────┘
                   │
                   ▼
           Deployment Plan
                   │
                   ▼
             Plan Validation
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
        READY    CONFIRM   BLOCKED
```

The architecture is designed to remain extensible as additional languages, frameworks, deployment strategies, and cloud capabilities are introduced.

---

# Development Phases

### Phase 1 — Repository Analysis

Understand what the developer built.

**Completed ✅**

### Phase 2 — Deployment Planning

Determine how the application should be deployed and whether enough information exists to proceed safely.

**Completed ✅**

### Phase 3 — Containerization

Convert validated deployment plans into production-ready container configurations and validate them.

**Next ⏳**

### Phase 4 — AWS Deployment

Push validated container images to Amazon ECR and deploy services to Amazon ECS.

**Planned**

### Phase 5 — Agentic Orchestration

Use LangGraph to coordinate analysis, planning, validation, checkpoints, retries, and controlled deployment execution.

**Planned**

### Phase 6 — Dashboard

Provide a React dashboard with real-time deployment progress, execution states, validation results, and logs.

**Planned**

---

# Technology Stack

## Current

* Python
* FastAPI
* Pydantic
* Pytest

## Infrastructure

* Docker
* AWS ECR
* AWS ECS
* Boto3

## Agentic Workflow

* LangGraph

## Frontend

* React
* WebSockets

---

# Reliability Principle

CloudForge follows an evidence-first approach.

> **A wrong infrastructure decision is worse than an explicit warning.**

The system should prefer:

```text
Known
  ↓
Evidence
  ↓
Decision
```

over:

```text
Assumption
  ↓
Guess
  ↓
Infrastructure change
```

When information is insufficient, CloudForge should report uncertainty and require confirmation rather than silently inventing deployment configuration.

This principle becomes increasingly important as CloudForge moves from analysis into automated infrastructure execution.

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
phase-4-complete
```

This allows later development phases to build on a known-good foundation without destabilizing earlier functionality.

---

# Current Milestone

```text
Phase 1 — Repository Analysis       🔒 COMPLETE
Phase 2 — Deployment Planning      🔒 COMPLETE
Phase 3 — Containerization         ⏳ NEXT
Phase 4 — AWS Deployment           ⏳
Phase 5 — Agentic Orchestration    ⏳
Phase 6 — Dashboard                ⏳
```

**Current next milestone: Phase 3 — Containerization**
