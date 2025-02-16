"""
Test raw http authorization used in Kubernetes Validating Webhooks.
"""

import base64

import openshift_client as oc
import pytest
from openshift_client import OpenShiftPythonException

from testsuite.certificates import CertInfo
from testsuite.kubernetes.ingress import Ingress
from testsuite.kuadrant.policy.authorization import ResourceAttributes, Value, ValueFrom, Pattern
from testsuite.kuadrant.policy.authorization.auth_config import AuthConfig
from testsuite.utils import cert_builder

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]

OPA_POLICY = """
    request := json.unmarshal(input.context.request.http.body).request
    verb := request.operation
    ingress := request.object { verb == "CREATE" }
    ingress := request.oldObject { verb == "DELETE" }
    forbidden { count(object.get(ingress.spec, "rules", [])) == 0 }
    rules { count(ingress.spec.rules) == 1; ingress.spec.rules[0] == {} }
    allow { rules; not forbidden }
"""


@pytest.fixture(scope="session")
def specific_authorino_name(blame):
    """Define specific name for authorino which matches with name in authorino certificate"""
    return blame("authorino")


@pytest.fixture(scope="module")
def authorino_domain(cluster, specific_authorino_name):
    """
    Hostname of the upstream certificate sent to be validated by APIcast
    May be overwritten to configure different test cases
    """
    return f"{specific_authorino_name}-authorino-authorization.{cluster.project}.svc"


@pytest.fixture(scope="module")
def certificates(cfssl, authorino_domain, wildcard_domain):
    """Certificate hierarchy used for the tests.
    Authorino certificate has *hosts* set to *authorino_domain* value.
    """
    chain = {
        "envoy_ca": CertInfo(children={"envoy_cert": None, "valid_cert": None}),
        "authorino_ca": CertInfo(
            children={
                "authorino_cert": CertInfo(hosts=authorino_domain),
            }
        ),
        "invalid_ca": CertInfo(children={"invalid_cert": None}),
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters, specific_authorino_name):
    """Setup TLS with specific name for authorino."""
    authorino_parameters["name"] = specific_authorino_name
    return authorino_parameters


@pytest.fixture(scope="module")
def authorization(authorization, cluster, authorino_domain) -> AuthConfig:
    """In case of Authorino, AuthConfig used for authorization"""

    # Authorino should have specific url so it is accessible by k8s webhook
    authorization.remove_all_hosts()
    authorization.add_host(authorino_domain)

    # get user info from admission webhook
    authorization.identity.clear_all()
    authorization.identity.add_plain("k8s-userinfo", "context.request.http.body.@fromstr|request.userInfo")

    # add OPA policy to process admission webhook request
    authorization.authorization.add_opa_policy("features", OPA_POLICY)
    user_value = ValueFrom("auth.identity.username")

    when = [
        Pattern("auth.authorization.features.allow", "eq", "true"),
        Pattern("auth.authorization.features.verb", "eq", "CREATE"),
    ]
    # add response for admission webhook for creating Ingress
    authorization.authorization.add_kubernetes(
        "ingress-authn-k8s-binding-create",
        user_value,
        ResourceAttributes(
            namespace=Value(cluster.project),
            group=Value("networking.k8s.io"),
            resource=Value("Ingress"),
            verb=Value("create"),
        ),
        when=when,
        priority=1,
    )

    when = [
        Pattern("auth.authorization.features.allow", "eq", "true"),
        Pattern("auth.authorization.features.verb", "eq", "DELETE"),
    ]
    # add response for admission webhook for deleting Ingress
    authorization.authorization.add_kubernetes(
        "ingress-authn-k8s-binding-delete",
        user_value,
        ResourceAttributes(
            namespace=Value(cluster.project),
            group=Value("networking.k8s.io"),
            resource=Value("Ingress"),
            verb=Value("delete"),
        ),
        when=when,
        priority=1,
    )
    return authorization


@pytest.fixture(scope="module", autouse=True)
def validating_webhook(cluster, authorino_domain, certificates, blame):
    """Create validating webhook."""
    name = blame("check-ingress") + ".authorino.kuadrant.io"
    service_name = authorino_domain.split(".")[0]

    cert_string = base64.b64encode(certificates["authorino_ca"].certificate.encode("ascii")).decode("ascii")
    model = {
        "apiVersion": "admissionregistration.k8s.io/v1",
        "kind": "ValidatingWebhookConfiguration",
        "metadata": {"name": name, "namespace": cluster.project},
        "webhooks": [
            {
                "name": name,
                "clientConfig": {
                    "service": {"namespace": cluster.project, "name": service_name, "port": 5001, "path": "/check"},
                    "caBundle": cert_string,
                },
                "rules": [
                    {
                        "apiGroups": ["networking.k8s.io"],
                        "apiVersions": ["v1"],
                        "resources": ["ingresses"],
                        "operations": ["CREATE", "UPDATE", "DELETE"],
                        "scope": "*",
                    }
                ],
                "sideEffects": "None",
                "admissionReviewVersions": ["v1"],
            }
        ],
    }

    webhook = None
    with cluster.context:
        webhook = oc.create(model)
    yield webhook
    with cluster.context:
        webhook.delete()


def test_authorized_via_http(cluster, blame):
    """Test raw http authorization via webhooks."""
    ingress = Ingress.create_instance(cluster, blame("minimal-ingress"), rules=[{}])
    ingress.commit()
    assert ingress.model.metadata.creationTimestamp
    ingress.delete()


def test_unauthorized_via_http(cluster, blame):
    """Test raw http authorization via webhooks but for unauthorized object."""
    ingress = Ingress.create_instance(cluster, blame("minimal-ingress"), rules=[{}, {}])
    with pytest.raises(OpenShiftPythonException, match="Unauthorized"):
        ingress.commit()
