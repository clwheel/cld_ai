#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Chris Wheeler (@clwheel)
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: support_level_info
short_description: Query Assisted Installer architecture and feature support levels
version_added: "0.1.0"
description:
  - Retrieve the support levels the Assisted Installer reports for CPU
    architectures and platform features, scoped to an OpenShift version.
  - One module covers the three support-level catalogs via O(kind) -
    V(architectures) (support level per CPU architecture), V(features)
    (support level per platform feature), and V(features_detailed) (full
    feature and operator details, including incompatibilities and operator
    dependencies).
  - This is a read-only C(_info) module. It never changes remote state and always
    reports C(changed=false).
author:
  - Chris Wheeler (@clwheel)
options:
  kind:
    description:
      - Which support-level catalog to query.
      - V(architectures) returns the support level per CPU architecture.
      - V(features) returns the support level per platform feature.
      - V(features_detailed) returns detailed feature and operator support
        entries.
    type: str
    choices: [architectures, features, features_detailed]
    required: true
  openshift_version:
    description:
      - The OpenShift version to query support levels for (for example V(4.16)).
      - Required by all three kinds; the API rejects the request without it.
    type: str
    required: true
  cpu_architecture:
    description:
      - CPU architecture used to scope the query. The API applies V(x86_64) when
        omitted.
      - Only valid when O(kind) is V(features) or V(features_detailed); the
        architectures catalog takes no architecture filter.
      - V(aarch64) is accepted by V(features) but not by V(features_detailed),
        which uses V(arm64).
    type: str
    choices: [x86_64, aarch64, arm64, ppc64le, s390x, multi]
  platform_type:
    description:
      - Provider platform type used to scope the query.
      - Only valid when O(kind) is V(features) or V(features_detailed).
    type: str
    choices: [baremetal, none, nutanix, vsphere, external]
  external_platform_name:
    description:
      - External platform name, used when O(platform_type=external). The API
        ignores it for any other platform type.
      - Only valid when O(kind) is V(features) or V(features_detailed).
    type: str
  api_token:
    description:
      - A short-lived Assisted Installer API access token (a bearer token).
      - If not set, the value of environment variable E(AI_API_TOKEN) is used.
      - Mutually complementary with O(offline_token); at least one source of
        credentials must resolve or the module fails fast.
    type: str
  offline_token:
    description:
      - A long-lived offline token used to obtain an access token via Red Hat SSO.
      - If not set, the value of environment variable E(AI_OFFLINE_TOKEN) is used.
    type: str
  timeout:
    description:
      - Timeout in seconds for the API request.
    type: int
    default: 30
notes:
  - Authenticates with the C(Authorization) bearer header against
    U(https://api.openshift.com/api/assisted-install/v2).
seealso:
  - name: Assisted Installer REST API
    description: Upstream OpenAPI specification for the Assisted Installer service.
    link: https://api.openshift.com/api/assisted-install/v2/openapi
"""

EXAMPLES = r"""
- name: List architecture support levels for an OpenShift version
  openshift_lab.assisted_installer.support_level_info:
    kind: architectures
    openshift_version: "4.16"
    api_token: "{{ assisted_installer_token }}"
  register: arch_levels

- name: Show the architecture support levels
  ansible.builtin.debug:
    var: arch_levels.architectures

- name: List feature support levels for a CPU architecture
  openshift_lab.assisted_installer.support_level_info:
    kind: features
    openshift_version: "4.16"
    cpu_architecture: arm64
    api_token: "{{ assisted_installer_token }}"

- name: List feature support levels for an external platform (token from AI_API_TOKEN env)
  openshift_lab.assisted_installer.support_level_info:
    kind: features
    openshift_version: "4.16"
    platform_type: external
    external_platform_name: oci

- name: Get detailed feature and operator support levels
  openshift_lab.assisted_installer.support_level_info:
    kind: features_detailed
    openshift_version: "4.16"
    cpu_architecture: x86_64
    platform_type: baremetal
    api_token: "{{ assisted_installer_token }}"
  register: detailed

- name: Count the fully supported features
  ansible.builtin.debug:
    msg: >-
      {{ detailed.detailed_features | selectattr('support_level', 'eq', 'supported')
         | list | length }} of {{ detailed.count }} features are supported
"""

RETURN = r"""
changed:
  description: Always V(false) - info modules never change state.
  returned: always
  type: bool
  sample: false
architectures:
  description:
    - Mapping of CPU architecture identifier to its support level.
    - Returned only when O(kind=architectures). Empty dict when nothing matches.
  returned: when O(kind=architectures)
  type: dict
  sample:
    X86_64_ARCHITECTURE: supported
    ARM64_ARCHITECTURE: supported
    MULTIARCH_RELEASE_IMAGE: tech-preview
features:
  description:
    - Mapping of feature identifier to its support level.
    - Returned only when O(kind=features). Empty dict when nothing matches.
  returned: when O(kind=features)
  type: dict
  sample:
    SNO: supported
    CNV: unsupported
    LVM: tech-preview
detailed_features:
  description:
    - Detailed feature support entries, including incompatibilities and the
      incompatibility reason when present.
    - Returned only when O(kind=features_detailed).
  returned: when O(kind=features_detailed)
  type: list
  elements: dict
  contains:
    feature-support-level-id:
      description: Feature identifier.
      type: str
      sample: SNO
    support_level:
      description: The feature's support level.
      type: str
      sample: supported
    incompatibilities:
      description: Feature identifiers incompatible with this feature.
      type: list
      elements: str
      sample:
        - BAREMETAL_PLATFORM
    reason:
      description: Reason for the support level, when the API provides one.
      type: str
      sample: cpuArchitecture
operators:
  description:
    - Operator support entries, including operator dependencies.
    - Returned only when O(kind=features_detailed).
  returned: when O(kind=features_detailed)
  type: list
  elements: dict
  contains:
    feature-support-level-id:
      description: Operator identifier.
      type: str
      sample: ODF
    name:
      description: Name of the operator.
      type: str
      sample: odf
    support_level:
      description: The operator's support level.
      type: str
      sample: supported
    dependencies:
      description: Feature identifiers this operator depends on.
      type: list
      elements: str
      sample:
        - LSO
    incompatibilities:
      description: Feature identifiers incompatible with this operator.
      type: list
      elements: str
    reason:
      description: Reason for the support level, when the API provides one.
      type: str
count:
  description:
    - Number of entries in the primary result for the chosen kind -
      architectures, features, or detailed_features.
  returned: success
  type: int
  sample: 3
"""

from ansible.module_utils.basic import AnsibleModule, env_fallback

from ..module_utils import assisted_installer as ai

# kind -> endpoint path (see docs/api-endpoint-map.md, "Catalog / read-only")
KIND_PATHS = {
    "architectures": "/support-levels/architectures",
    "features": "/support-levels/features",
    "features_detailed": "/support-levels/features/detailed",
}

# Query parameters that only the features endpoints accept.
FEATURES_ONLY_PARAMS = ("cpu_architecture", "platform_type", "external_platform_name")


def main():
    module = AnsibleModule(
        argument_spec=dict(
            kind=dict(
                type="str",
                required=True,
                choices=["architectures", "features", "features_detailed"],
            ),
            openshift_version=dict(type="str", required=True),
            cpu_architecture=dict(
                type="str",
                choices=["x86_64", "aarch64", "arm64", "ppc64le", "s390x", "multi"],
            ),
            platform_type=dict(
                type="str",
                choices=["baremetal", "none", "nutanix", "vsphere", "external"],
            ),
            external_platform_name=dict(type="str"),
            api_token=dict(
                type="str", no_log=True, fallback=(env_fallback, ["AI_API_TOKEN"])
            ),
            offline_token=dict(
                type="str", no_log=True, fallback=(env_fallback, ["AI_OFFLINE_TOKEN"])
            ),
            timeout=dict(type="int", default=30),
        ),
        supports_check_mode=True,
    )

    kind = module.params["kind"]

    # Fail fast when features-only filters are combined with the architectures
    # catalog: the endpoint has no such query parameters, so silently dropping
    # them would return unfiltered results the user believes were scoped.
    if kind == "architectures":
        unsupported = [
            name for name in FEATURES_ONLY_PARAMS if module.params.get(name)
        ]
        if unsupported:
            module.fail_json(
                msg="%s only apply when kind is 'features' or 'features_detailed', "
                    "not 'architectures'" % ", ".join(unsupported)
            )

    token = ai.resolve_token(module)

    query = {"openshift_version": module.params["openshift_version"]}
    if kind != "architectures":
        # Unset values are dropped by the shared client's URL builder.
        for name in FEATURES_ONLY_PARAMS:
            query[name] = module.params.get(name)

    data, info = ai.request(
        module,
        "GET",
        KIND_PATHS[kind],
        token,
        query=query,
        timeout=module.params["timeout"],
    )

    status = info.get("status")
    if status != 200:
        module.fail_json(
            msg="Failed to retrieve %s support levels (HTTP %s)" % (kind, status),
            status=status,
            body=data,
        )

    result = {"changed": False}
    if kind == "architectures":
        levels = data if isinstance(data, dict) else {}
        # The API wraps the map under "architectures"; unwrap defensively.
        if isinstance(levels.get("architectures"), dict):
            levels = levels["architectures"]
        result["architectures"] = levels
        result["count"] = len(levels)
    elif kind == "features":
        levels = data if isinstance(data, dict) else {}
        # The API wraps the map under "features"; unwrap defensively. The key is
        # checked to be a dict so a list-valued "features" (the detailed
        # endpoint's shape) is never mistaken for this endpoint's map.
        if isinstance(levels.get("features"), dict):
            levels = levels["features"]
        result["features"] = levels
        result["count"] = len(levels)
    else:  # features_detailed returns two lists, not maps.
        payload = data if isinstance(data, dict) else {}
        features = payload.get("features")
        operators = payload.get("operators")
        if not isinstance(features, list) or not isinstance(operators, list):
            module.fail_json(
                msg="Detailed support levels API returned an invalid response body",
                body=data,
            )
        result["detailed_features"] = features
        result["operators"] = operators
        result["count"] = len(features)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
