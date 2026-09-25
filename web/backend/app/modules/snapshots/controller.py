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
            parse = session.q.fileParseStatus().answer(snapshot=context.engine_snapshot).dict()
            issues = session.q.initIssues().answer(snapshot=context.engine_snapshot).dict()
            warnings = session.q.parseWarning().answer(snapshot=context.engine_snapshot).dict()
            conversion = (
                session.q.viConversionWarning().answer(snapshot=context.engine_snapshot).dict()
            )
            return InitializationAnswer(
                parse_status=parse["answerElements"][0].get("rows", []),
                issues=issues["answerElements"][0].get("rows", []),
                parse_warnings=warnings["answerElements"][0].get("rows", []),
                conversion_warnings=conversion["answerElements"][0].get("rows", []),
                engine_version=session.get_component_versions()["Batfish"],
                sdk_version=version("pybatfish"),
            )

    def deletion_presence(self, context, *, remove=False):
        with self._sessions.exclusive(owner=str(context.snapshot_id)) as session:
            if context.engine_network not in session.list_networks():
                return False
            # Public session context attribute avoids set_network's create-if-absent behavior.
            session.network = context.engine_network
            exists = context.engine_snapshot in session.list_snapshots()
            if remove and exists:
                session.delete_snapshot(context.engine_snapshot)
                exists = context.engine_snapshot in session.list_snapshots()
                if exists:
                    raise RuntimeError("Remote deletion is not confirmed")
            return exists
