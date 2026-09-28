"""Direct SDK regression for selecting a named ACL in a real snapshot."""

import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from app.modules.analysis.controller import normalize
from tests import test_filters
from tests.test_inventory import initialize

filter_app = test_filters.filter_app


@pytest.mark.integration
def test_literal_acl_name_resolves_to_only_the_selected_filter(filter_app):
    state = initialize(filter_app, files=test_filters.acl_files())
    _, database, app, _, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        database, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )
    with sessions.for_job(context) as session:
        answer = normalize(
            session.q.resolveFilterSpecifier(nodes="c2", filters="WEB-TEST")
            .answer(snapshot=context.engine_snapshot)
            .dict()
        )["answerElements"][0]
    assert [row["Filter_Name"] for row in answer["rows"]] == ["WEB-TEST"]
