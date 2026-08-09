from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NodeRole(StrEnum):
    AGENT = "agent"
    NODE = "node"
    DEVELOPMENT = "development"


class EventModePolicy(StrEnum):
    EVENT = "event"
    REHEARSAL = "rehearsal"
    DEVELOPMENT = "development"


class NetworkPolicy(StrEnum):
    OFFLINE = "offline"
    LOCAL_ONLY = "local_only"
    OPTIONAL = "optional"


class SourceBindingConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    path: str
    maximum_candidates: int = Field(default=1000, ge=1, le=100_000)
    allowed_extensions: tuple[str, ...] = (
        ".mov",
        ".mp4",
        ".mkv",
        ".mxf",
        ".wav",
    )

    @field_validator("key", "path")
    @classmethod
    def non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("path")
    @classmethod
    def absolute_bounded_path(cls, value: str) -> str:
        windows = PureWindowsPath(value)
        posix = PurePosixPath(value)
        if not windows.is_absolute() and not posix.is_absolute():
            raise ValueError("source path must be absolute")
        if ".." in windows.parts or ".." in posix.parts:
            raise ValueError("source path cannot contain parent traversal")
        return value

    @field_validator("allowed_extensions")
    @classmethod
    def normalized_extensions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({item.strip().casefold() for item in value}))
        if not normalized or any(not item.startswith(".") or len(item) < 2 for item in normalized):
            raise ValueError("allowed_extensions must contain dot-prefixed extensions")
        return normalized


class StageDeploymentConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    external_references: dict[str, str] = Field(default_factory=dict)
    sources: tuple[SourceBindingConfiguration, ...]

    @field_validator("key", "name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @model_validator(mode="after")
    def unique_sources(self) -> StageDeploymentConfiguration:
        keys = [source.key for source in self.sources]
        if not keys:
            raise ValueError("Stage requires at least one source binding")
        if len(keys) != len(set(keys)):
            raise ValueError("Stage source binding keys must be unique")
        return self


class EventDeploymentConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    external_references: dict[str, str] = Field(default_factory=dict)
    stages: tuple[StageDeploymentConfiguration, ...]

    @field_validator("key", "name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @model_validator(mode="after")
    def unique_stages_and_sources(self) -> EventDeploymentConfiguration:
        stage_keys = [stage.key for stage in self.stages]
        if not stage_keys:
            raise ValueError("Event requires at least one Stage")
        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError("Stage keys must be unique")
        source_keys = [source.key for stage in self.stages for source in stage.sources]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("A source binding key can belong to only one Stage")
        return self


class ResourceLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    maximum_concurrent_assessments: int = Field(default=2, ge=1, le=64)
    maximum_cpu_percentage: int = Field(default=20, ge=1, le=100)
    maximum_memory_bytes: int = Field(default=536_870_912, ge=1)
    minimum_stable_seconds: int = Field(default=5, ge=1, le=3600)


class KernelDeploymentConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    deployment_id: str
    node_id: str
    node_role: NodeRole
    event_mode: EventModePolicy = EventModePolicy.EVENT
    network_policy: NetworkPolicy = NetworkPolicy.OPTIONAL
    postgres_dsn_secret_ref: str
    event: EventDeploymentConfiguration
    resources: ResourceLimits = Field(default_factory=ResourceLimits)
    schedule_source_reference: str | None = None

    @field_validator(
        "schema_version",
        "deployment_id",
        "node_id",
        "postgres_dsn_secret_ref",
    )
    @classmethod
    def non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @model_validator(mode="after")
    def supported_schema_and_network(self) -> KernelDeploymentConfiguration:
        if self.schema_version != "1.0":
            raise ValueError("Unsupported Kernel deployment schema version")
        if self.event_mode is EventModePolicy.EVENT and self.network_policy not in {
            NetworkPolicy.OFFLINE,
            NetworkPolicy.LOCAL_ONLY,
            NetworkPolicy.OPTIONAL,
        }:
            raise ValueError("Event mode cannot require continuous Internet access")
        return self


class EffectiveKernelConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    deployment: KernelDeploymentConfiguration
    postgres_dsn: str = Field(repr=False)
    sources: Mapping[str, str]
    field_sources: Mapping[str, str]

    @field_validator("postgres_dsn")
    @classmethod
    def dsn_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Resolved PostgreSQL DSN must not be empty")
        return value

    @field_validator("sources", "field_sources")
    @classmethod
    def freeze_sources(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return MappingProxyType(dict(sorted(value.items())))

    def redacted_summary(self) -> dict[str, object]:
        return {
            "schema_version": self.deployment.schema_version,
            "deployment_id": self.deployment.deployment_id,
            "node_id": self.deployment.node_id,
            "node_role": self.deployment.node_role.value,
            "event_mode": self.deployment.event_mode.value,
            "network_policy": self.deployment.network_policy.value,
            "event_key": self.deployment.event.key,
            "stage_keys": tuple(stage.key for stage in self.deployment.event.stages),
            "source_binding_keys": tuple(sorted(self.sources)),
            "postgres_dsn": "<redacted>",
            "postgres_dsn_source": self.deployment.postgres_dsn_secret_ref,
            "field_sources": dict(self.field_sources),
        }


def load_kernel_deployment_configuration(
    path: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> EffectiveKernelConfiguration:
    env = os.environ if environment is None else environment
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)

    deployment = KernelDeploymentConfiguration.model_validate(raw)
    overrides: dict[str, object] = {}
    field_sources = {
        "node_role": "toml",
        "event_mode": "toml",
        "network_policy": "toml",
        "event": "toml",
        "sources": "toml",
        "postgres_dsn": f"environment:{deployment.postgres_dsn_secret_ref}",
    }
    if role := env.get("STAGEFLOW_NODE_ROLE"):
        overrides["node_role"] = role
        field_sources["node_role"] = "environment:STAGEFLOW_NODE_ROLE"
    if event_mode := env.get("STAGEFLOW_EVENT_MODE"):
        overrides["event_mode"] = event_mode
        field_sources["event_mode"] = "environment:STAGEFLOW_EVENT_MODE"
    if network := env.get("STAGEFLOW_NETWORK_POLICY"):
        overrides["network_policy"] = network
        field_sources["network_policy"] = "environment:STAGEFLOW_NETWORK_POLICY"
    if overrides:
        deployment = deployment.model_copy(update=overrides)
        deployment = KernelDeploymentConfiguration.model_validate(deployment.model_dump())

    secret_name = deployment.postgres_dsn_secret_ref
    dsn = env.get(secret_name)
    if dsn is None or not dsn.strip():
        raise ValueError(f"PostgreSQL secret reference {secret_name!r} is unresolved.")
    sources = {
        source.key: source.path
        for stage in deployment.event.stages
        for source in stage.sources
    }
    return EffectiveKernelConfiguration(
        deployment=deployment,
        postgres_dsn=dsn,
        sources=sources,
        field_sources=field_sources,
    )


__all__ = [
    "EffectiveKernelConfiguration",
    "EventDeploymentConfiguration",
    "EventModePolicy",
    "KernelDeploymentConfiguration",
    "NetworkPolicy",
    "NodeRole",
    "ResourceLimits",
    "SourceBindingConfiguration",
    "StageDeploymentConfiguration",
    "load_kernel_deployment_configuration",
]
