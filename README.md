# CloudForge

**AI-Assisted Cloud Deployment Orchestration Engine**

CloudForge is a platform designed to reduce the infrastructure burden on developers by analyzing their application repositories and orchestrating the deployment process to AWS.

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

The deployment workflow will use explicit checkpoints and validation rather than blindly deploying generated infrastructure.

## Current Status

### Phase 1 — Repository Analysis ✅

The current implementation focuses exclusively on understanding an application repository.

CloudForge can currently:

* Discover relevant repository files
* Detect application services
* Parse supported project manifests
* Normalize dependencies
* Detect languages, runtimes, and frameworks
* Identify likely application entry points
* Detect application ports
* Identify environment variables without exposing secret values
* Analyze existing Docker configuration
* Detect external dependencies
* Build evidence-based service relationships
* Attach confidence and evidence to important inferences
* Handle unknown and ambiguous repositories conservatively

Currently validated against representative:

* MERN applications
* Python/FastAPI applications
* Multi-manifest Python services
* Next.js applications
* Multi-service repositories
* Unknown/unsupported repositories
* Malformed manifests
* Different environment-variable naming conventions

## Technology Stack

### Backend

* Python
* FastAPI
* Pydantic

### Planned Infrastructure

* Docker
* AWS ECR
* AWS ECS
* Boto3

### Planned Agentic Workflow

* LangGraph

### Planned Frontend

* React
* WebSockets

## Architecture

The current repository-analysis architecture separates:

```text
Repository Discovery
        ↓
Manifest Parsing
        ↓
Dependency Normalization
        ↓
Service Resolution
        ↓
Technology Detection
        ↓
Source Analysis
        ↓
Environment Analysis
        ↓
Docker Analysis
        ↓
External Dependency Analysis
        ↓
Relationship Analysis
        ↓
Structured Repository Model
```

The architecture is designed to be extensible so that additional languages, frameworks, manifest formats, and analysis capabilities can be added without rewriting the core analyzer.

## Development Phases

### Phase 1 — Repository Analysis

Understand what the developer built. **Completed.**

### Phase 2 — Deployment Planning

Convert repository analysis into an evidence-backed deployment plan.

### Phase 3 — Containerization

Generate and validate Docker configurations and container images.

### Phase 4 — AWS Deployment

Push images to Amazon ECR and deploy services to Amazon ECS.

### Phase 5 — Agentic Orchestration

Use LangGraph to coordinate analysis, planning, validation, retries, and deployment.

### Phase 6 — Dashboard

Provide a React dashboard with real-time deployment progress and execution logs.

## Development Principle

CloudForge should prefer:

**Evidence over assumptions.**

When the repository does not provide enough information to make a reliable inference, CloudForge should report uncertainty rather than inventing a deployment decision.

This principle is especially important because later phases will use the analysis results to make infrastructure decisions.

## Current Phase

**Phase 1 — Repository Analysis: Complete**

The next milestone is:

**Phase 2 — Deployment Planning**
