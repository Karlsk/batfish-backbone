import csv
import io
import json
from uuid import UUID

import pytest

from tests import test_networks

export_app = test_networks.network_app


@pytest.mark.parametrize(
    "value", ["=1+1", "+SUM(A1)", "-1", "@x", "\t =1", "\r\n@x", "\ufeff+1", "\x00-1"]
)
def test_csv_formula_and_unicode(value):
    from app.modules.results.export import csv_cell

    assert csv_cell(" " * 100000 + "=1") == "'" + " " * 100000 + "=1"
    assert csv_cell(value) == "'" + value
    assert csv_cell('中文\n第二行,"字段"') == '中文\n第二行,"字段"'
    assert csv_cell({"name": "中文"}) == '{"name":"中文"}'


@pytest.mark.integration
def test_export_preserves_context(export_app, monkeypatch):
    from app.contracts.results import Column, StructuredAnswer
    from app.modules.analysis.controller import AnalysisController
    from tests.test_snapshots import create, setup

    client, db, app, headers, network, source, actor = setup(export_app)
    created = create(client, headers, network, source).json()
    context = app.state.jobs_service.get(actor, UUID(created["job_id"])).context
    answer = StructuredAnswer(
        kind="table",
        columns=(Column(key="value", label="名称", type="String"),),
        rows=({"value": "=1+1"}, {"value": '中文\n第二行,"字段"'}),
    )
    with db.transaction() as tx:
        result = app.state.results_service.publish(
            context,
            answer,
            parameters={"options": {"nodes": "r1"}},
            quality={"coverage": "limited"},
            cache_key=None,
            transaction=tx,
        )
    monkeypatch.setattr(
        AnalysisController, "run", lambda *a, **k: pytest.fail("Export must not execute SDK")
    )
    url = f"/api/v1/results/{result.id}/export"
    response = client.get(url, params={"format": "json"})
    assert response.status_code == 200
    assert response.json()["metadata"] == client.get(f"/api/v1/results/{result.id}").json()
    assert response.json()["data"]["rows"] == [dict(row) for row in answer.rows]
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="batfish-{result.id}.json"'
    )
    assert response.headers["cache-control"] == "private, no-store"
    exported = client.get(url, params={"format": "csv"})
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0] == ["record_type", "metadata_json", "data:value"]
    assert json.loads(rows[1][1]) == response.json()["metadata"]
    assert rows[2] == ["data", "", "'=1+1"]
    assert rows[3][2] == '中文\n第二行,"字段"'
    assert client.get(url, params={"format": "xlsx"}).status_code == 422
    assert (
        client.get("/api/v1/results/00000000-0000-0000-0000-000000000000/export").status_code == 404
    )
    client.cookies.clear()
    assert client.get(url).status_code == 401


@pytest.mark.integration
def test_trace_csv_rejected(export_app):
    from app.contracts.results import StructuredAnswer
    from tests.test_snapshots import create, setup

    client, db, app, headers, network, source, actor = setup(export_app)
    created = create(client, headers, network, source).json()
    context = app.state.jobs_service.get(actor, UUID(created["job_id"])).context
    answer = StructuredAnswer(
        kind="traces",
        columns=(),
        rows=(
            {
                "Flow": {"ingressNode": "r1"},
                "Traces": [{"disposition": "NO_ROUTE", "hops": []}],
                "TraceCount": 2,
            },
        ),
    )
    with db.transaction() as tx:
        result = app.state.results_service.publish(
            context,
            answer,
            parameters={},
            quality={"coverage": "unknown"},
            cache_key=None,
            transaction=tx,
        )
    url = f"/api/v1/results/{result.id}/export"
    assert client.get(url, params={"format": "csv"}).status_code == 409
    value = client.get(url).json()
    assert (
        value["metadata"]["truncated"] and value["metadata"]["truncation_reason"] == "trace_limit"
    )
    assert value["data"]["flows"][0]["traces"][0]["disposition"] == "NO_ROUTE"


def test_streaming_json_batches_small_tokens_without_losing_unicode():
    from app.modules.results.export import buffered_chunks

    payload = {"rows": [{"Node": "中文", "Network": "10.0.0.0/24"}] * 10000}
    chunks = list(buffered_chunks(json.JSONEncoder(ensure_ascii=False).iterencode(payload)))
    assert len(chunks) < 20
    assert all(0 < len(chunk) <= 65536 for chunk in chunks)
    assert json.loads(b"".join(chunks)) == payload
