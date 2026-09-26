"""Config-domain aggregate contract (AES101 `_aggregate`).

``IConfigAggregate`` is the single entry point over the config feature.
The CLI/MCP surfaces and the sibling orchestrators call
:meth:`execute`; the agent behind it owns the sandbox probe and the
request-timeout environment override, so no surface can obtain a config
that ignores the operator's environment.

Four capability seams back the verbs, declared in
``contract_config_protocol.py``: the environment probe
(``IConfigEnvironmentProtocol``), the config validator
(``IConfigValidatorProtocol``), the path resolver
(``IConfigPathResolverProtocol``), and the host-capacity advisor
(``IConfigCapacityProtocol``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_core_vo import ConfigRequest, ConfigResponse


class IConfigAggregate(ABC):
    """Single entry point over the config feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a variant to ``ConfigRequest``, not a second
    aggregate method.
    """

    @abstractmethod
    def execute(self, request: ConfigRequest) -> ConfigResponse:
        """Build the runtime configuration *request* asks for and return it."""
        ...


__all__ = ["IConfigAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IConfigAggregate": IConfigAggregate,
}
