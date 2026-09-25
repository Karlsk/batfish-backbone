from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.source_lines import source_lines
from app.modules.auth.service import AuthService
from app.modules.networks.service import NetworksService
from app.modules.uploads.repository import UploadsRepository, UploadStore
from app.modules.uploads.schemas import UploadDTO, UploadInput, UploadLimits, UploadManifest


class UploadsService:
    def __init__(self, database, auth: AuthService, networks: NetworksService, settings):
        self._database, self._auth, self._networks = database, auth, networks
        self._store = UploadStore(settings.data_dir)
        self.limits = UploadLimits(
            settings.upload_max_bytes, settings.upload_max_expanded_bytes, settings.upload_max_files
        )
        self._ttl = settings.upload_ttl_seconds

    @property
    def storage_root(self):
        self._store.ensure_root()
        return self._store.root

    def create(
        self, actor: Actor, network_id: UUID, inputs: list[UploadInput], *, archive=False
    ) -> UploadDTO:
        actor = self._auth.revalidate_actor(actor)
        self._networks.require_ready(actor, network_id)
        identifier = uuid4()
        with self._store.prepare(identifier, inputs, archive=archive, limits=self.limits) as (
            files,
            digest,
            publish,
        ):
            dto = UploadDTO(
                id=identifier,
                network_id=network_id,
                owner_id=actor.user_id,
                storage_key=str(identifier),
                content_hash=digest,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
                manifest=UploadManifest(
                    upload_id=identifier,
                    network_id=network_id,
                    storage_key=str(identifier),
                    files=files,
                    content_hash=digest,
                ),
            )
            with self._database.transaction() as transaction:
                UploadsRepository(transaction).add(dto)
                publish()
        return dto

    def consume(
        self, actor: Actor, network_id: UUID, upload_id: UUID, *, transaction=None
    ) -> UploadManifest:
        actor = self._auth.revalidate_actor(actor)
        self._networks.require_ready(actor, network_id)
        with (
            nullcontext(transaction) if transaction is not None else self._database.transaction()
        ) as transaction:
            repository = UploadsRepository(transaction)
            row = repository.locked(upload_id)
            if row is None or row.network_id != network_id:
                raise ServiceError(ErrorCode.NOT_FOUND)
            if row.owner_id != actor.user_id and actor.role != "admin":
                raise ServiceError(ErrorCode.FORBIDDEN)
            now = datetime.now(UTC)
            if row.consumed_at is not None or row.expires_at <= now:
                raise ServiceError(ErrorCode.CONFLICT)
            repository.mark_consumed(upload_id, now)
            return row.manifest.model_copy(update={"content_hash": row.content_hash})

    def materialize(self, manifest: UploadManifest):
        """Internal service capability: recreate verified logical paths for an SDK upload."""
        return self._store.materialize(manifest)

    def cleanup_expired(self) -> int:
        now = datetime.now(UTC)
        with self._database.transaction() as transaction:
            repository = UploadsRepository(transaction)
            rows = repository.expired(now)
            for row in rows:
                self._store.remove(row.storage_key)
                repository.remove(row)
            count = len(rows)
        with self._database.transaction() as transaction:
            referenced = UploadsRepository(transaction).storage_keys()
        self._store.cleanup_orphans(referenced, now=now, ttl_seconds=self._ttl)
        return count

    def read_file(self, manifest: UploadManifest, file_id: UUID, *, offset=0, limit=50):
        # Called only with a server-stored snapshot manifest after resource authorization.
        from app.contracts.uploads import FilePage, SourceLine

        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        entry = next((entry for entry in manifest.files if entry.id == file_id), None)
        if entry is None:
            raise ServiceError(ErrorCode.NOT_FOUND)
        entry = self._file_metadata(manifest, entry)
        lines, warnings = [], set()
        with self._store.open_verified(manifest, entry) as source:
            if entry.encoding == "binary":
                warnings.add("BINARY_CONTENT_NOT_DISPLAYABLE")
            else:
                for number, data, truncated in source_lines(source):
                    if number <= offset:
                        continue
                    if number > offset + limit:
                        break
                    try:
                        value = data.decode(entry.encoding)
                    except UnicodeDecodeError:
                        value = data.decode(entry.encoding, errors="replace")
                        warnings.add("DECODING_REPLACEMENT")
                    if truncated:
                        warnings.add("LONG_LINE_TRUNCATED")
                    lines.append(SourceLine(number=number, text=value, truncated=truncated))
        return FilePage(
            file_id=entry.id,
            path=entry.path,
            encoding=entry.encoding,
            lines=tuple(lines),
            offset=offset,
            limit=limit,
            total=entry.line_count,
            warnings=tuple(sorted(warnings)),
        )

    def _file_metadata(self, manifest, entry):
        if entry.line_policy == "lf-v0" and entry.encoding != "binary":
            with self._store.open_verified(manifest, entry) as source:
                count = sum(1 for _ in source_lines(source, max_bytes=0))
            return entry.model_copy(update={"line_count": count, "line_policy": "crlf-v1"})
        return entry

    def describe_files(self, manifest):
        return tuple(self._file_metadata(manifest, entry) for entry in manifest.files)
