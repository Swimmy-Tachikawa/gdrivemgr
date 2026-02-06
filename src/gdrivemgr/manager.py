"""GoogleDriveManager: orchestrates Local planning and Drive apply (v1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from gdrivemgr.auth import AuthInfo
from gdrivemgr.controller import GoogleDriveController
from gdrivemgr.errors import (
    ApiError,
    AuthError,
    ConflictError,
    GDriveMgrError,
    InvalidArgumentError,
    InvalidStateError,
    NetworkError,
    NotFoundError,
    PermissionError,
    QuotaExceededError,
    RateLimitError,
)
from gdrivemgr.local import GoogleDriveLocal
from gdrivemgr.models import OperationResult, SyncResult
from gdrivemgr.plan import Action, PlanOperation, SyncPlan
from gdrivemgr.plan.preconditions import check_modified_time_precondition
from gdrivemgr.util.mime import is_folder


@dataclass(frozen=True)
class _ApplyContext:
    id_map: dict[str, str]


class GoogleDriveManager:
    """High-level manager for safe sync: Plan -> Apply."""

    def __init__(
        self,
        auth_info: AuthInfo,
        *,
        scopes: Optional[Sequence[str]] = None,
        supports_all_drives: bool = True,
    ) -> None:
        self._controller = GoogleDriveController(
            auth_info,
            scopes=scopes,
            supports_all_drives=supports_all_drives,
        )
        self._local: Optional[GoogleDriveLocal] = None
        self._remote_root_id: Optional[str] = None

    @classmethod
    def from_controller(cls, controller: GoogleDriveController) -> "GoogleDriveManager":
        """Create manager with an injected controller (useful for tests)."""
        obj = cls.__new__(cls)
        obj._controller = controller
        obj._local = None
        obj._remote_root_id = None
        return obj

    @property
    def local(self) -> GoogleDriveLocal:
        """Return the current local view. Requires open() first."""
        if self._local is None:
            raise InvalidStateError("Local is not initialized. Call open() first.")
        return self._local

    def open(self, remote_root_id: str) -> GoogleDriveLocal:
        """
        Load Drive subtree under remote_root_id and build GoogleDriveLocal.

        Raises:
            InvalidStateError: if pending ops exist (must apply/clear first).
            InvalidArgumentError: if remote_root_id is not a folder.
        """
        if self._local is not None and self._local.list_ops():
            raise InvalidStateError("Pending operations exist. Apply/clear first.")

        root = self._controller.get(remote_root_id)
        if not is_folder(root.mime_type):
            raise InvalidArgumentError("remote_root_id must be a folder")

        # Treat as scope root: clear parents to avoid linking outside.
        root.parents = []

        descendants = self._controller.list_tree(remote_root_id, include_trashed=False)
        file_infos = [root] + [f for f in descendants if not f.trashed]

        local = GoogleDriveLocal.from_file_infos(remote_root_id, file_infos)
        self._local = local
        self._remote_root_id = remote_root_id
        return local

    def refresh_snapshot(self) -> None:
        """Reload the current root snapshot. Requires open() first."""
        if self._remote_root_id is None:
            raise InvalidStateError("No root opened. Call open() first.")
        if self._local is not None and self._local.list_ops():
            raise InvalidStateError("Pending operations exist. Apply/clear first.")
        self.open(self._remote_root_id)

    def build_plan(self) -> SyncPlan:
        """Build a SyncPlan from current local pending operations."""
        return self.local.build_plan()

    def sync(self, *, execute: bool = False) -> SyncPlan | SyncResult:
        """
        Convenience API.

        - execute=False: build and return SyncPlan
        - execute=True: build, apply, and return SyncResult
        """
        plan = self.build_plan()
        if not execute:
            return plan
        return self.apply_plan(plan)

    def apply_plan(self, plan: SyncPlan) -> SyncResult:
        """
        Apply SyncPlan to Drive.

        Policy:
            - Fail-fast for non-fatal errors: return SyncResult.failed (no raise).
            - Raise for fatal errors: Auth/Permission/InvalidArgument/InvalidState.
            - After apply attempt: clear local ops and try to refresh snapshot.
        """
        if self._remote_root_id is None or self._local is None:
            raise InvalidStateError("No root opened. Call open() first.")
        if plan.remote_root_id != self._remote_root_id:
            raise InvalidStateError("Plan root_id does not match current opened root.")

        ops_by_id = _index_operations(plan.operations)
        _validate_apply_order(plan.apply_order, ops_by_id)

        ctx = _ApplyContext(id_map={})
        results: list[OperationResult] = []
        stopped_op_id: Optional[str] = None

        for op_id in plan.apply_order:
            op = ops_by_id[op_id]
            try:
                op.validate_required_fields()
            except ValueError as exc:
                raise InvalidArgumentError(
                    "Invalid operation: missing required fields",
                    details={"op_id": op.op_id, "action": op.action.value},
                    cause=exc,
                ) from exc

            try:
                self._apply_one(op, ctx)
                results.append(_success_result(op, ctx))
            except GDriveMgrError as exc:
                if _is_fatal(exc):
                    raise
                results.append(_failed_result(op, exc))
                stopped_op_id = op.op_id
                break

        status = "failed" if stopped_op_id is not None else "success"
        summary = _summarize_results(results)

        # Clear pending ops regardless of success/failure.
        self._local.clear_ops()

        # Always attempt refresh snapshot (do not raise on refresh failure).
        snapshot_refreshed = True
        try:
            self.open(plan.remote_root_id)
        except Exception:
            snapshot_refreshed = False
            summary["refresh_failed"] = summary.get("refresh_failed", 0) + 1

        return SyncResult(
            status=status,  # type: ignore[arg-type]
            stopped_op_id=stopped_op_id,
            results=results,
            id_map=dict(ctx.id_map),
            summary=summary,
            snapshot_refreshed=snapshot_refreshed,
        )

    # ----------------------------
    # Internals
    # ----------------------------
    def _apply_one(self, op: PlanOperation, ctx: _ApplyContext) -> None:
        """Apply one operation. Raises gdrivemgr errors on failure."""
        # Precondition check (modified_time only).
        if op.precondition and op.target_local_id:
            target_file_id = self._resolve_file_id(op.target_local_id, ctx)
            actual = self._controller.get(target_file_id).modified_time
            check_modified_time_precondition(op.precondition, actual)

        if op.action is Action.CREATE_FOLDER:
            parent_id = self._resolve_file_id(op.parent_local_id, ctx)
            info = self._controller.create_folder(op.name, parent_id)  # type: ignore[arg-type]
            _store_created_id(ctx, op.result_local_id, info.file_id)
            return

        if op.action is Action.COPY:
            src_id = self._resolve_file_id(op.target_local_id, ctx)
            parent_id = self._resolve_file_id(op.new_parent_local_id, ctx)
            info = self._controller.copy(src_id, parent_id, new_name=op.name)
            _store_created_id(ctx, op.result_local_id, info.file_id)
            return

        if op.action is Action.RENAME:
            file_id = self._resolve_file_id(op.target_local_id, ctx)
            self._controller.rename(file_id, op.name)  # type: ignore[arg-type]
            return

        if op.action is Action.MOVE:
            file_id = self._resolve_file_id(op.target_local_id, ctx)
            parent_id = self._resolve_file_id(op.new_parent_local_id, ctx)
            self._controller.move(file_id, parent_id)
            return

        if op.action is Action.TRASH:
            file_id = self._resolve_file_id(op.target_local_id, ctx)
            self._controller.trash(file_id)
            return

        if op.action is Action.DELETE_PERMANENT:
            file_id = self._resolve_file_id(op.target_local_id, ctx)
            self._controller.delete_permanently(file_id)
            return

        if op.action is Action.UPLOAD_FILE:
            parent_id = self._resolve_file_id(op.parent_local_id, ctx)
            info = self._controller.upload_file(
                op.local_path,  # type: ignore[arg-type]
                parent_id,
                name=op.name,
            )
            _store_created_id(ctx, op.result_local_id, info.file_id)
            return

        if op.action is Action.DOWNLOAD_FILE:
            file_id = self._resolve_file_id(op.target_local_id, ctx)
            self._controller.download_file(
                file_id,
                op.local_path,  # type: ignore[arg-type]
                overwrite=bool(op.overwrite),
            )
            return

        raise InvalidArgumentError("Unsupported action", details={"action": op.action})

    def _resolve_file_id(self, local_id: Optional[str], ctx: _ApplyContext) -> str:
        if not local_id:
            raise InvalidStateError("local_id is missing")

        if local_id in ctx.id_map:
            return ctx.id_map[local_id]

        info = self.local.get(local_id)
        if info.file_id:
            return info.file_id

        raise InvalidStateError(
            "Unresolved local_id (Drive file_id not known yet)",
            details={"local_id": local_id},
        )


def _store_created_id(ctx: _ApplyContext, result_local_id: Optional[str], file_id: str | None) -> None:
    if not result_local_id:
        raise InvalidStateError("result_local_id is missing for create-like operation")
    if not file_id:
        raise InvalidStateError("Drive did not return file_id for created item")
    ctx.id_map[result_local_id] = file_id


def _index_operations(operations: list[PlanOperation]) -> dict[str, PlanOperation]:
    ops_by_id: dict[str, PlanOperation] = {}
    for op in operations:
        if op.op_id in ops_by_id:
            raise InvalidArgumentError("Duplicate op_id in plan", details={"op_id": op.op_id})
        ops_by_id[op.op_id] = op
    return ops_by_id


def _validate_apply_order(apply_order: list[str], ops_by_id: dict[str, PlanOperation]) -> None:
    for op_id in apply_order:
        if op_id not in ops_by_id:
            raise InvalidArgumentError(
                "apply_order contains unknown op_id",
                details={"op_id": op_id},
            )


def _is_fatal(exc: GDriveMgrError) -> bool:
    return isinstance(
        exc,
        (
            AuthError,
            PermissionError,
            InvalidArgumentError,
            InvalidStateError,
        ),
    )


def _success_result(op: PlanOperation, ctx: _ApplyContext) -> OperationResult:
    result_file_id = None
    if op.result_local_id and op.result_local_id in ctx.id_map:
        result_file_id = ctx.id_map[op.result_local_id]

    return OperationResult(
        op_id=op.op_id,
        seq=op.seq,
        action=op.action.value,
        status="success",
        result_local_id=op.result_local_id,
        result_file_id=result_file_id,
    )


def _failed_result(op: PlanOperation, exc: GDriveMgrError) -> OperationResult:
    return OperationResult(
        op_id=op.op_id,
        seq=op.seq,
        action=op.action.value,
        status="failed",
        error_type=exc.__class__.__name__,
        error_message=str(exc),
        error_details=getattr(exc, "details", None),
    )


def _summarize_results(results: list[OperationResult]) -> dict[str, int]:
    summary: dict[str, int] = {"success": 0, "failed": 0, "skipped": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return summary
