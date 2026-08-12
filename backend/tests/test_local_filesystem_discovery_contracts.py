from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest
from local_filesystem_discovery_fixtures import (
    ADAPTER_ID,
    CONFIGURED_AT,
    IDENTITY_NAMESPACE_ID,
    make_adapter,
    make_policy,
)

from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemDiscoveryConfiguration,
    LocalFilesystemEligibilityPolicy,
    LocalFilesystemExtensionMatchingMode,
    LocalFilesystemHiddenEntryPolicy,
    LocalFilesystemSymlinkPolicy,
    LocalFilesystemTargetBinding,
)
from app.contexts.production.runtime import RuntimeSourceLocationScheme


def test_configuration_binding_and_policy_are_frozen_and_serialization_ready(
    tmp_path: Path,
) -> None:
    caller_metadata: dict[str, object] = {"nested": {"values": [1, 2]}}
    adapter, _ = make_adapter(tmp_path)
    configuration = replace(adapter.configuration, metadata=caller_metadata)
    nested = cast(dict[str, object], caller_metadata["nested"])
    values = cast(list[int], nested["values"])
    values.append(3)

    assert configuration.adapter_id == ADAPTER_ID
    assert configuration.adapter_version == "1.0.0"
    assert configuration.identity_namespace_id == IDENTITY_NAMESPACE_ID
    assert configuration.configured_at == CONFIGURED_AT
    assert isinstance(configuration.metadata, MappingProxyType)
    assert configuration.metadata["nested"]["values"] == (1, 2)
    assert isinstance(configuration.target_bindings, tuple)
    assert isinstance(
        configuration.target_bindings[0].eligibility_policy.metadata,
        MappingProxyType,
    )
    with pytest.raises(FrozenInstanceError):
        configuration.adapter_version = "2.0"  # type: ignore[misc]
    with pytest.raises(TypeError):
        configuration.metadata["changed"] = True  # type: ignore[index]


def test_configuration_requires_aware_time_unique_targets_and_supported_schemes(
    tmp_path: Path,
) -> None:
    adapter, _ = make_adapter(tmp_path)
    configuration = adapter.configuration
    binding = configuration.target_bindings[0]

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(configuration, configured_at=datetime(2026, 7, 17, 10, 5))
    with pytest.raises(ValueError, match="One collection target"):
        replace(
            configuration,
            target_bindings=(binding, replace(binding, binding_id=IDENTITY_NAMESPACE_ID)),
        )
    with pytest.raises(ValueError, match="only local_file and mounted_volume"):
        replace(
            configuration,
            supported_source_schemes=(RuntimeSourceLocationScheme.NETWORK_SHARE,),
        )


@pytest.mark.parametrize("entry_limit", [0, -1])
def test_binding_requires_positive_entry_bound(tmp_path: Path, entry_limit: int) -> None:
    adapter, _ = make_adapter(tmp_path)
    with pytest.raises(ValueError, match="positive"):
        replace(
            adapter.configuration.target_bindings[0],
            maximum_directory_entries_examined=entry_limit,
        )


@pytest.mark.parametrize(
    "location_kind, message",
    [
        ("relative/recordings", "absolute"),
        ("parent_traversal", "parent traversal"),
        ("wildcard", "glob or wildcard"),
        ("credential", "credential"),
        ("null_byte", "null byte"),
    ],
)
def test_binding_rejects_unbounded_or_credential_bearing_locations(
    tmp_path: Path,
    location_kind: str,
    message: str,
) -> None:
    adapter, _ = make_adapter(tmp_path)
    absolute_root = Path(tmp_path.anchor) / "recordings"
    locations = {
        "relative/recordings": "relative/recordings",
        "parent_traversal": str(absolute_root / ".." / "escape"),
        "wildcard": str(absolute_root / "*.mov"),
        "credential": str(absolute_root / "clip.mov?access_token=secret"),
        "null_byte": str(absolute_root / "clip\x00.mov"),
    }
    with pytest.raises(ValueError, match=message):
        replace(
            adapter.configuration.target_bindings[0],
            configured_absolute_target_location=locations[location_kind],
        )


def test_policy_has_no_hidden_extension_or_symlink_defaults() -> None:
    policy = make_policy()

    assert policy.allowed_filename_extensions == (".mov", ".mp4")
    assert policy.extension_matching_mode is LocalFilesystemExtensionMatchingMode.CASE_INSENSITIVE
    assert policy.hidden_entry_policy is LocalFilesystemHiddenEntryPolicy.EXCLUDE
    assert policy.regular_file_required is True
    assert policy.symlink_policy is LocalFilesystemSymlinkPolicy.REJECT_OR_SKIP
    assert policy.permit_all_regular_files is False
    assert policy.excluded_suffixes == (".partial",)


def test_policy_requires_allowlist_or_deliberate_allow_all() -> None:
    with pytest.raises(ValueError, match="allowlist or deliberate allow-all"):
        LocalFilesystemEligibilityPolicy(
            allowed_filename_extensions=(),
            extension_matching_mode=LocalFilesystemExtensionMatchingMode.CASE_SENSITIVE,
            hidden_entry_policy=LocalFilesystemHiddenEntryPolicy.INCLUDE,
            regular_file_required=True,
            symlink_policy=LocalFilesystemSymlinkPolicy.REJECT_OR_SKIP,
            permit_all_regular_files=False,
        )
    allow_all = LocalFilesystemEligibilityPolicy(
        allowed_filename_extensions=(),
        extension_matching_mode=LocalFilesystemExtensionMatchingMode.CASE_SENSITIVE,
        hidden_entry_policy=LocalFilesystemHiddenEntryPolicy.INCLUDE,
        regular_file_required=True,
        symlink_policy=LocalFilesystemSymlinkPolicy.REJECT_OR_SKIP,
        permit_all_regular_files=True,
    )
    assert allow_all.permit_all_regular_files is True


def test_contract_metadata_rejects_credentials(tmp_path: Path) -> None:
    adapter, _ = make_adapter(tmp_path)
    with pytest.raises(ValueError, match="credential"):
        replace(adapter.configuration, metadata={"access_token": "not-retained"})
    with pytest.raises(ValueError, match="credential"):
        replace(
            adapter.configuration.target_bindings[0],
            metadata={"nested": {"password": "not-retained"}},
        )


def test_request_reference_rejects_credentials(tmp_path: Path) -> None:
    _adapter, request = make_adapter(tmp_path)

    with pytest.raises(ValueError, match="credential"):
        replace(request, target_reference="/recordings?access_token=not-retained")


def test_configuration_ids_must_match_runtime_without_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _ = make_adapter(tmp_path)
    def fail_filesystem(_path: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr("os.lstat", fail_filesystem)
    monkeypatch.setattr("os.scandir", fail_filesystem)

    reconstructed = type(adapter)(adapter.runtime, adapter.configuration)

    assert reconstructed.configuration == adapter.configuration
    with pytest.raises(ValueError, match="Runtime ID"):
        type(adapter)(
            adapter.runtime,
            replace(
                adapter.configuration,
                runtime_id=IDENTITY_NAMESPACE_ID,
                target_bindings=(
                    replace(
                        adapter.configuration.target_bindings[0],
                        runtime_id=IDENTITY_NAMESPACE_ID,
                    ),
                ),
            ),
        )


def test_configuration_public_contracts_contain_no_path_objects(tmp_path: Path) -> None:
    adapter, _ = make_adapter(tmp_path)
    binding: LocalFilesystemTargetBinding = adapter.configuration.target_bindings[0]
    configuration: LocalFilesystemDiscoveryConfiguration = adapter.configuration

    assert isinstance(binding.configured_absolute_target_location, str)
    assert all(
        isinstance(scheme, RuntimeSourceLocationScheme)
        for scheme in configuration.supported_source_schemes
    )
