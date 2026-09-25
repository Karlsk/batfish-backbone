from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
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
                ),
            )
            with self._database.transaction() as transaction:
                UploadsRepository(transaction).add(dto)
                publish()
        return dto

    def consume(self, actor: Actor, network_id: UUID, upload_id: UUID) -> UploadManifest:
        actor = self._auth.revalidate_actor(actor)
        self._networks.require_ready(actor, network_id)
        with self._database.transaction() as transaction:
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
            return row.manifest

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
