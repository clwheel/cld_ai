# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Wheeler (@clwheel)
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the support_level_info module.

The API is mocked at the fetch_url layer (per CLAUDE.md): we patch
``...module_utils.assisted_installer.fetch_url`` so the REAL shared client runs
(URL building, query encoding, JSON parsing, status handling) while no live
call is ever made.
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.openshift_lab.assisted_installer.plugins.modules import (
    support_level_info,
)
from ansible_collections.openshift_lab.assisted_installer.plugins.module_utils import (
    assisted_installer as ai,
)

from ansible_helpers import (
    AnsibleExitJson,
    AnsibleFailJson,
    fake_fetch_url,
    patch_ansible,
    set_module_args,
)

# A representative slice of the real GET /support-levels/architectures response.
SAMPLE_ARCHITECTURES = {
    "architectures": {
        "X86_64_ARCHITECTURE": "supported",
        "ARM64_ARCHITECTURE": "supported",
        "MULTIARCH_RELEASE_IMAGE": "tech-preview",
    }
}

# A representative slice of the real GET /support-levels/features response.
SAMPLE_FEATURES = {
    "features": {
        "SNO": "supported",
        "CNV": "unsupported",
        "LVM": "tech-preview",
    }
}

# A representative slice of the real GET /support-levels/features/detailed response.
SAMPLE_DETAILED = {
    "features": [
        {
            "feature-support-level-id": "SNO",
            "support_level": "supported",
            "incompatibilities": ["BAREMETAL_PLATFORM"],
            "reason": "cpuArchitecture",
        },
        {
            "feature-support-level-id": "CNV",
            "support_level": "unsupported",
            "incompatibilities": [],
        },
    ],
    "operators": [
        {
            "feature-support-level-id": "ODF",
            "name": "odf",
            "support_level": "supported",
            "dependencies": ["LSO"],
            "incompatibilities": [],
        },
    ],
}

BASE_ARGS = {"kind": "features", "openshift_version": "4.16", "api_token": "t"}


def _run(monkeypatch, status=200, body=None, args=None, calls=None):
    """Drive the module once and return the raised Exit/Fail exception."""
    patch_ansible(monkeypatch)
    # Never let an ambient token leak into a test that means to have none.
    monkeypatch.delenv("AI_API_TOKEN", raising=False)
    monkeypatch.delenv("AI_OFFLINE_TOKEN", raising=False)
    monkeypatch.setattr(ai, "fetch_url", fake_fetch_url(status=status, body=body, calls=calls))
    set_module_args(args or {})
    try:
        support_level_info.main()
    except (AnsibleExitJson, AnsibleFailJson) as exc:
        return exc
    raise AssertionError("module did not call exit_json or fail_json")


# --- lifecycle / idempotency -------------------------------------------------


def test_architectures_returns_map_and_is_never_changed(monkeypatch):
    # Run twice: a read-only info module is idempotent, so a second identical
    # run must also report changed=False (per CLAUDE.md testing posture).
    def _once():
        exc = _run(
            monkeypatch,
            body=SAMPLE_ARCHITECTURES,
            args=dict(BASE_ARGS, kind="architectures"),
        )
        assert isinstance(exc, AnsibleExitJson)
        assert exc.result["changed"] is False
        assert exc.result["architectures"] == SAMPLE_ARCHITECTURES["architectures"]
        assert exc.result["count"] == 3
        # Only the architectures field is returned for this kind.
        assert "features" not in exc.result
        assert "detailed_features" not in exc.result
        assert "operators" not in exc.result

    _once()  # first run
    _once()  # second (idempotent) run — still changed=False


def test_features_returns_map(monkeypatch):
    exc = _run(monkeypatch, body=SAMPLE_FEATURES, args=dict(BASE_ARGS))
    assert isinstance(exc, AnsibleExitJson)
    assert exc.result["changed"] is False
    assert exc.result["features"] == SAMPLE_FEATURES["features"]
    assert exc.result["count"] == 3
    assert "architectures" not in exc.result
    assert "operators" not in exc.result


def test_features_detailed_returns_lists(monkeypatch):
    exc = _run(
        monkeypatch,
        body=SAMPLE_DETAILED,
        args=dict(BASE_ARGS, kind="features_detailed"),
    )
    assert isinstance(exc, AnsibleExitJson)
    assert exc.result["changed"] is False
    assert exc.result["detailed_features"] == SAMPLE_DETAILED["features"]
    assert exc.result["operators"] == SAMPLE_DETAILED["operators"]
    assert exc.result["count"] == 2  # primary result is the features list
    assert "architectures" not in exc.result
    assert "features" not in exc.result


def test_unwrapped_map_body_is_tolerated(monkeypatch):
    # The shared unwrap is defensive: a body that is already the bare map
    # (no "features" envelope) is returned as-is.
    bare_map = SAMPLE_FEATURES["features"]
    exc = _run(monkeypatch, body=bare_map, args=dict(BASE_ARGS))
    assert isinstance(exc, AnsibleExitJson)
    assert exc.result["features"] == bare_map


def test_unwrapped_architectures_body_is_tolerated(monkeypatch):
    # Same defensive unwrap for the architectures kind.
    bare_map = SAMPLE_ARCHITECTURES["architectures"]
    exc = _run(
        monkeypatch, body=bare_map, args=dict(BASE_ARGS, kind="architectures")
    )
    assert isinstance(exc, AnsibleExitJson)
    assert exc.result["architectures"] == bare_map


def test_non_dict_map_body_returns_empty(monkeypatch):
    # A body that is not an object cannot yield a map; the tolerant default is
    # an empty result, matching openshift_version_info's handling.
    exc = _run(monkeypatch, body=["not", "a", "map"], args=dict(BASE_ARGS))
    assert isinstance(exc, AnsibleExitJson)
    assert exc.result["features"] == {}
    assert exc.result["count"] == 0


# --- API contract: paths, query encoding, auth --------------------------------


def test_architectures_query_carries_only_the_version(monkeypatch):
    calls = []
    _run(
        monkeypatch,
        body=SAMPLE_ARCHITECTURES,
        args=dict(BASE_ARGS, kind="architectures"),
        calls=calls,
    )
    assert len(calls) == 1
    url = calls[0]["url"]
    assert "/support-levels/architectures?" in url
    assert "openshift_version=4.16" in url
    # The architectures endpoint has no architecture/platform filters.
    assert "cpu_architecture" not in url
    assert "platform_type" not in url
    assert "external_platform_name" not in url


def test_features_query_params_reach_the_url(monkeypatch):
    calls = []
    _run(
        monkeypatch,
        body=SAMPLE_FEATURES,
        args=dict(
            BASE_ARGS,
            cpu_architecture="arm64",
            platform_type="external",
            external_platform_name="oci",
        ),
        calls=calls,
    )
    url = calls[0]["url"]
    assert "/support-levels/features?" in url
    assert "openshift_version=4.16" in url
    assert "cpu_architecture=arm64" in url
    assert "platform_type=external" in url
    assert "external_platform_name=oci" in url


def test_unset_features_filters_are_omitted_from_query(monkeypatch):
    calls = []
    _run(monkeypatch, body=SAMPLE_FEATURES, args=dict(BASE_ARGS), calls=calls)
    url = calls[0]["url"]
    assert "openshift_version=4.16" in url
    assert "cpu_architecture" not in url
    assert "platform_type" not in url
    assert "external_platform_name" not in url


def test_features_detailed_uses_detailed_path(monkeypatch):
    calls = []
    _run(
        monkeypatch,
        body=SAMPLE_DETAILED,
        args=dict(BASE_ARGS, kind="features_detailed"),
        calls=calls,
    )
    assert "/support-levels/features/detailed?" in calls[0]["url"]


def test_uses_get_and_authorizes(monkeypatch):
    calls = []
    _run(monkeypatch, body=SAMPLE_FEATURES, args=dict(BASE_ARGS, api_token="sekret"), calls=calls)
    assert calls[0]["method"] == "GET"
    assert calls[0]["headers"]["Authorization"] == "Bearer sekret"


# --- check mode ---------------------------------------------------------------


def test_check_mode_still_reads_and_reports_unchanged(monkeypatch):
    # A read-only info module is safe in check mode: it may GET, must not mutate,
    # and always reports changed=False.
    calls = []
    exc = _run(
        monkeypatch,
        body=SAMPLE_FEATURES,
        args=dict(BASE_ARGS, _ansible_check_mode=True),
        calls=calls,
    )
    assert isinstance(exc, AnsibleExitJson)
    assert exc.result["changed"] is False
    assert all(c["method"] == "GET" for c in calls)


# --- safety guards ------------------------------------------------------------


def test_architectures_rejects_features_only_params(monkeypatch):
    # The architectures endpoint has no cpu_architecture/platform_type/
    # external_platform_name query params; passing them must fail fast rather
    # than silently return unfiltered results.
    calls = []
    exc = _run(
        monkeypatch,
        body=SAMPLE_ARCHITECTURES,
        args=dict(BASE_ARGS, kind="architectures", platform_type="vsphere"),
        calls=calls,
    )
    assert isinstance(exc, AnsibleFailJson)
    assert "platform_type" in exc.result["msg"]
    assert "architectures" in exc.result["msg"]
    # Fail-fast: bail before any HTTP request is attempted.
    assert calls == []


def test_architectures_rejects_cpu_architecture_filter(monkeypatch):
    calls = []
    exc = _run(
        monkeypatch,
        body=SAMPLE_ARCHITECTURES,
        args=dict(BASE_ARGS, kind="architectures", cpu_architecture="arm64"),
        calls=calls,
    )
    assert isinstance(exc, AnsibleFailJson)
    assert "cpu_architecture" in exc.result["msg"]
    assert calls == []


def test_auth_fail_fast_when_no_token(monkeypatch):
    calls = []
    exc = _run(
        monkeypatch,
        body=SAMPLE_FEATURES,
        args={"kind": "features", "openshift_version": "4.16"},
        calls=calls,
    )
    assert isinstance(exc, AnsibleFailJson)
    assert "token" in exc.result["msg"].lower()
    # Fail-fast: bail before any HTTP request is attempted.
    assert calls == []


# --- API contract: error mapping ----------------------------------------------


def test_non_200_fails_with_status(monkeypatch):
    exc = _run(
        monkeypatch,
        status=400,
        body={"reason": "Invalid openshift_version"},
        args=dict(BASE_ARGS),
    )
    assert isinstance(exc, AnsibleFailJson)
    assert exc.result["status"] == 400
    assert "features" in exc.result["msg"]  # the message names the kind


def test_detailed_body_with_non_list_features_fails(monkeypatch):
    # The detailed endpoint's contract is two lists; anything else is a body
    # shape violation, not an empty result.
    exc = _run(
        monkeypatch,
        body={"features": {"SNO": "supported"}, "operators": []},
        args=dict(BASE_ARGS, kind="features_detailed"),
    )
    assert isinstance(exc, AnsibleFailJson)
    assert "invalid response body" in exc.result["msg"]


def test_detailed_body_missing_operators_fails(monkeypatch):
    exc = _run(
        monkeypatch,
        body={"features": []},
        args=dict(BASE_ARGS, kind="features_detailed"),
    )
    assert isinstance(exc, AnsibleFailJson)
    assert "invalid response body" in exc.result["msg"]
