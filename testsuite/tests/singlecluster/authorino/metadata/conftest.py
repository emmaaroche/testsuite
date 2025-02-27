"""Conftest for metadata feature tests"""

import pytest

from testsuite.kubernetes import KubernetesObject


@pytest.fixture(scope="module")
def create_client_secret(request, cluster, authorino):
    """Creates Client Secret, used by Authorino to start the authentication with the UMA registry"""

    def _create_secret(name, client_id, client_secret):
        model = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": authorino.namespace()},
            "stringData": {"clientID": client_id, "clientSecret": client_secret},
            "type": "Opaque",
        }
        secret = KubernetesObject(model, context=cluster.context)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret
