import json
from importlib.metadata import version

from app.infrastructure.sdk import SessionFactory
from app.modules.snapshots.schemas import InitializationAnswer


class SnapshotController:
    def __init__(self, database, settings):
        self._sessions = SessionFactory(database, settings)

    def initialize(self, context, manifest, options):
        # manifest is a service-materialized private directory, never a caller path.
        with self._sessions.for_job(context, select_snapshot=False) as session:
            session.init_snapshot(
                str(manifest),
                name=context.engine_snapshot,
                overwrite=False,
                extra_args={
                    "ignoremanagementinterfaces": options.ignore_management_interfaces,
                    "parsereuse": options.parse_reuse,
                },
            )
            parse = session.q.fileParseStatus().answer(snapshot=context.engine_snapshot).frame()
            issues = session.q.initIssues().answer(snapshot=context.engine_snapshot).frame()
            engine_version = session.get_component_versions()["Batfish"]
            return InitializationAnswer(
                parse_status=json.loads(parse.to_json(orient="records", default_handler=str)),
                issues=json.loads(issues.to_json(orient="records", default_handler=str)),
                engine_version=engine_version,
                sdk_version=version("pybatfish"),
            )
