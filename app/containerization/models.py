from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EnvironmentVariableRequirement(BaseModel):
    name: str
    service: str
    required: bool = True
    secret: bool = False
    source: str | None = None
    source_type: str | None = None
    value: str | None = None


class ContainerizationServicePlan(BaseModel):
    service_name: str
    name: str | None = None
    service_path: str | None = None
    runtime: str | None = None
    framework: str | None = None
    base_runtime_requirement: str | None = None
    working_directory: str | None = None
    dependency_install_command: str | None = None
    build_command: str | None = None
    start_command: str | None = None
    production_serving_strategy: str | None = None
    entry_point: str | None = None
    application_port: int | str | None = None
    port: int | str | None = None
    environment_variable_requirements: list[EnvironmentVariableRequirement] = Field(default_factory=list)
    deployment_type: Literal["container"] = "container"
    container_command: str | None = None
    container_arguments: list[str] = Field(default_factory=list)
    build_context: str | None = None
    relevant_source_files: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    containerization_readiness: Literal["ready", "requires_confirmation", "blocked"] = "requires_confirmation"
    containerization_ready: bool = False


class ContainerizationPlan(BaseModel):
    repository: dict[str, Any] = Field(default_factory=dict)
    services: list[ContainerizationServicePlan] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    containerization_readiness: Literal["ready", "requires_confirmation", "blocked"] = "requires_confirmation"
    containerization_ready: bool = False


class DockerExecutionResult(BaseModel):
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    success: bool = False
    error: str | None = None
    image_tag: str | None = None
    container_id: str | None = None


class DockerServiceValidationResult(BaseModel):
    service_name: str
    validation_status: Literal["ready", "requires_confirmation", "blocked", "skipped", "failed"] = "skipped"
    build_status: Literal["success", "failed", "skipped", "requires_confirmation", "blocked", "docker_unavailable"] = "skipped"
    runtime_status: Literal["success", "failed", "skipped", "requires_confirmation", "blocked", "docker_unavailable"] = "skipped"
    valid: bool = False
    image_tag: str | None = None
    container_id: str | None = None
    build_logs: str = ""
    runtime_logs: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    cleanup_status: Literal["success", "failed", "skipped"] = "skipped"
    assumptions: list[str] = Field(default_factory=list)
    reason: str | None = None


class DockerValidationResult(BaseModel):
    services: list[DockerServiceValidationResult] = Field(default_factory=list)
    validation_status: Literal["ready", "requires_confirmation", "blocked", "skipped", "failed"] = "blocked"
    valid: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
