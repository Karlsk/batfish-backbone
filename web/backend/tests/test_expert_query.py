from uuid import UUID

import pytest

from tests import test_networks
from tests.test_inventory import initialize

expert_app = test_networks.network_app


def test_catalog_includes_strict_request_schema():
    from app.modules.analysis.registry import Registry

    catalog = {entry.id: entry for entry in Registry().capabilities()}
    nodes = catalog["nodes"]
    assert nodes.parameters_schema["properties"]["options"]
    assert nodes.parameters_schema["additionalProperties"] is False
    assert list(catalog["search-filters"].parameters_schema["required"]) == [
        "nodes",
        "filters",
        "options",
    ]


@pytest.mark.integration
def test_expert_equivalent_to_dedicated(expert_app):
    client, _, app, headers, network, snapshot, actor = initialize(expert_app)
    base = f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses"
    parameters = {"options": {"properties": ["Hostname"]}}
    dedicated = client.post(base + "/nodes", json=parameters, headers=headers)
    assert dedicated.status_code == 202, dedicated.text
    assert app.state.execution_service.run_once("worker")
    dedicated_job = app.state.jobs_service.get(actor, UUID(dedicated.json()["id"]))
    assert dedicated_job.status == "succeeded"
    expert = client.post(
        base + "/query",
        json={"question_id": "nodes", "parameters": parameters},
        headers=headers,
    )
    assert expert.status_code == 202, expert.text
    assert app.state.execution_service.run_once("worker")
    expert_job = app.state.jobs_service.get(actor, UUID(expert.json()["id"]))
    assert expert_job.status == "succeeded"
    assert expert_job.result_id == dedicated_job.result_id
    assert expert_job.effective_parameters == dedicated_job.effective_parameters
    result = client.get(f"/api/v1/results/{expert_job.result_id}").json()
    assert result["effective_parameters"]["operation"] == "nodes"
    assert client.get(f"/api/v1/results/{expert_job.result_id}/rows").json()["total"] == 4


@pytest.mark.integration
def test_arbitrary_method_rejected(expert_app):
    client, _, _, headers, network, snapshot, _ = initialize(expert_app)
    base = f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/query"
    for body in [
        {"question_id": "__import__", "parameters": {}},
        {"question_id": "fileParseStatus", "parameters": {}},
        {"question_id": "nodes", "parameters": {"options": {"host": "foreign"}}},
        {"question_id": "nodes", "parameters": {"snapshot_id": "other"}},
        {"question_id": "nodes", "parameters": {}, "sdk_method": "delete_network"},
    ]:
        response = client.post(base, json=body, headers=headers)
        assert response.status_code == 422, (body, response.text)


def test_disabled_registered_capability_rejected():
    from app.contracts.errors import ErrorCode, ServiceError
    from app.modules.analysis.registry import Registry
    from app.modules.analysis.schemas import Entry

    registry = Registry(entries=[Entry("disabled", "Disabled")])
    with pytest.raises(ServiceError) as error:
        registry.validate("disabled", {})
    assert error.value.code == ErrorCode.CONFLICT
