"""Public Pybatfish adapter for immutable outage forks."""

from importlib.metadata import version

from pybatfish.datamodel import Interface

from app.contracts.snapshots import InitializationAnswer
from app.infrastructure.sdk import SessionFactory


class FaultScenarioController:
    def __init__(self, database, settings):
        self._sessions = SessionFactory(database, settings)

    def fork(self, context, request):
        with self._sessions.for_job(context, select_snapshot=False) as session:
            name = session.fork_snapshot(
                base_name=context.engine_reference_snapshot,
                name=context.engine_snapshot,
                overwrite=False,
                deactivate_nodes=list(request.deactivate_nodes),
                deactivate_interfaces=[
                    Interface(hostname=item.node, interface=item.interface)
                    for item in request.deactivate_interfaces
                ],
            )
            if name != context.engine_snapshot:
                # A returned name is a definitive SDK answer. Leave the engine
                # gate cleanly, then let the service report the failed task.
                return None
            parse = session.q.fileParseStatus().answer(snapshot=name).dict()
            issues = session.q.initIssues().answer(snapshot=name).dict()
            warnings = session.q.parseWarning().answer(snapshot=name).dict()
            conversion = session.q.viConversionWarning().answer(snapshot=name).dict()
            return InitializationAnswer(
                parse_status=parse["answerElements"][0].get("rows", []),
                issues=issues["answerElements"][0].get("rows", []),
                parse_warnings=warnings["answerElements"][0].get("rows", []),
                conversion_warnings=conversion["answerElements"][0].get("rows", []),
                engine_version=session.get_component_versions()["Batfish"],
                sdk_version=version("pybatfish"),
            )
