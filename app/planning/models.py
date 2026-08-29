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


class ServiceRelationship(BaseModel):
    source: str
    target: str
    relationship: str
    deployment_implication: str
    confidence: float | None = None
    evidence: list[str] = Field(default_factory=list)


class ContainerRequirements(BaseModel):
    runtime: str | None = None
    working_directory: str | None = None
    port: int | str | None = None
    entry_point: str | None = None
    build_command: str | None = None
    start_command: str | None = None
    command: str | None = None


class ServiceDeploymentPlan(BaseModel):
    name: str
    service_path: str
    deployment_type: Literal["container"] = "container"
    runtime: str | None = None
    framework: str | None = None
    dependency_install_command: str | None = None
    build_command: str | None = None
    build_strategy: str | None = None
    start_command: str | None = None
    production_serving_strategy: str | None = None
    entry_point: str | None = None
    port: int | str | None = None
    required_environment_variables: list[EnvironmentVariableRequirement] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    service_relationships: list[ServiceRelationship] = Field(default_factory=list)
    container_requirements: ContainerRequirements = Field(default_factory=ContainerRequirements)
    exposure: str = "unknown"
    deployment_readiness: Literal["ready", "requires_confirmation", "blocked"] = "requires_confirmation"
    deployment_ready: bool = False
    warnings: list[str] = Field(default_factory=list)


class ExternalDependencyPlan(BaseModel):
    name: str
    type: str
    service: str | None = None
    confidence: float | None = None
    evidence: list[str] = Field(default_factory=list)


class NetworkingPlan(BaseModel):
    service_ports: list[dict[str, Any]] = Field(default_factory=list)
    service_to_service_communication: list[dict[str, Any]] = Field(default_factory=list)
    external_access: list[str] = Field(default_factory=list)
    dependency_connectivity: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AwsTargetPlan(BaseModel):
    provider: Literal["AWS"] = "AWS"
    registry: Literal["ECR"] = "ECR"
    compute: Literal["ECS"] = "ECS"


class DeploymentPlan(BaseModel):
    repository: dict[str, Any]
    services: list[ServiceDeploymentPlan] = Field(default_factory=list)
    external_dependencies: list[ExternalDependencyPlan] = Field(default_factory=list)
    networking: NetworkingPlan = Field(default_factory=NetworkingPlan)
    environment: dict[str, Any] = Field(default_factory=dict)
    container_requirements: dict[str, Any] = Field(default_factory=dict)
    aws_target: AwsTargetPlan = Field(default_factory=AwsTargetPlan)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    deployment_readiness: Literal["ready", "requires_confirmation", "blocked"] = "requires_confirmation"
    deployment_ready: bool = False
