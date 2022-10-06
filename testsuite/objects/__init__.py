"""Module containing base classes for common objects"""
import abc
from dataclasses import dataclass
from typing import Literal


@dataclass
class Rule:
    """
    Data class for authorization rules represented by simple pattern-matching expressions.
    Args:
        :param selector: that is fetched from the Authorization JSON
        :param operator: `eq` (equals), `neq` (not equal), `incl` (includes) and `excl` (excludes), for arrays
                         `matches`, for regular expressions
        :param value: a fixed comparable value
    """

    selector: str
    operator: Literal["eq", "neq", "incl", "excl", "matches"]
    value: str


class LifecycleObject(abc.ABC):
    """Any objects which has its lifecycle controlled by create() and delete() methods"""

    @abc.abstractmethod
    def commit(self):
        """Commits resource.
        if there is some reconciliation needed, the method should wait until it is all reconciled"""

    @abc.abstractmethod
    def delete(self):
        """Removes resource,
        if there is some reconciliation needed, the method should wait until it is all reconciled"""


class Authorino(LifecycleObject):
    """Authorino instance"""

    @abc.abstractmethod
    def wait_for_ready(self):
        """True, if after some waiting the Authorino is ready"""

    @property
    @abc.abstractmethod
    def authorization_url(self):
        """Authorization URL that can be plugged into envoy"""


class Authorization(LifecycleObject):
    """Object containing Authorization rules and configuration for either Authorino or Kuadrant"""

    @abc.abstractmethod
    def add_oidc_identity(self, name, endpoint, credentials, selector):
        """Adds OIDC identity provider"""

    @abc.abstractmethod
    def add_api_key_identity(self, name, all_namespaces, match_label, match_expression,  credentials, selector):
        """Adds API Key identity"""

    @abc.abstractmethod
    def add_anonymous_identity(self, name):
        """Adds anonymous identity"""

    @abc.abstractmethod
    def add_mtls_identity(self, name: str, selector_key: str, selector_value: str):
        """Adds mTLS identity"""

    @abc.abstractmethod
    def remove_all_identities(self):
        """Removes all identities from AuthConfig"""

    @abc.abstractmethod
    def add_host(self, hostname):
        """Adds host"""

    @abc.abstractmethod
    def remove_host(self, hostname):
        """Remove host"""

    @abc.abstractmethod
    def remove_all_hosts(self):
        """Remove host"""

    @abc.abstractmethod
    def add_opa_policy(self, name, rego_policy):
        """Adds OPA inline Rego policy"""

    @abc.abstractmethod
    def add_external_opa_policy(self, name, endpoint, ttl):
        """Adds OPA policy from external registry"""

    @abc.abstractmethod
    def add_response(self, response):
        """Add response to AuthConfig"""

    @abc.abstractmethod
    def add_auth_rule(self, name: str, rule: Rule, when: Rule, metrics: bool, priority: int):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""

    @abc.abstractmethod
    def add_role_rule(self, name: str, role: str, path: str, metrics: bool, priority: int):
        """Adds a rule, which allows access to 'path' only to users with 'role'"""

    @abc.abstractmethod
    def remove_all_rules(self):
        """Removes all rules from AuthConfig"""

    @abc.abstractmethod
    def set_deny_with(self, code, value):
        """Set denyWith to authconfig"""

    @abc.abstractmethod
    def add_http_metadata(self, name, endpoint, method):
        """Set metadata http external auth feature"""

    @abc.abstractmethod
    def add_user_info_metadata(self, name, identity_source):
        """Set metadata OIDC user info"""


class PreexistingAuthorino(Authorino):
    """Authorino which is already deployed prior to the testrun"""

    def __init__(self, authorization_url) -> None:
        super().__init__()
        self._authorization_url = authorization_url

    def wait_for_ready(self):
        return True

    @property
    def authorization_url(self):
        return self._authorization_url

    def commit(self):
        return

    def delete(self):
        return
