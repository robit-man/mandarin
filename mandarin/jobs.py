"""Bounded jobs, confined workers, durable states and safe publication."""

from __future__ import annotations

import concurrent.futures
import json
import hashlib
import os
import queue
import shutil
import signal
import sqlite3
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .files import file_identity, publish
from .operations import BY_ID, validate_options
from .runtime import python_command, sandbox_command, worker_environment


class Canceled(Exception):
    pass


@dataclass
class Job:
    id: str
    operation: str
    inputs: list[Path]
    options: dict
    destination: Path
    beside_sources: bool = False
    state: str = "queued"
    progress: float = 0
    message: str = "Waiting"
    outputs: list[Path] = field(default_factory=list)
    error: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event)
    process: subprocess.Popen | None = None


class JobManager:
    def __init__(self, state_dir: Path | None = None, callback=None):
        self.state_dir = (
            state_dir
            or Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
            / "mandarin"
        )
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.callback = callback or (lambda job: None)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.state_dir / "jobs.sqlite3", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, operation TEXT, inputs TEXT, options TEXT, destination TEXT, state TEXT, outputs TEXT, error TEXT, updated REAL)"
        )
        self.db.execute(
            "UPDATE jobs SET state='interrupted', error='The application stopped before this job completed.' WHERE state IN ('queued','running','validating','publishing')"
        )
        self.db.execute(
            "DELETE FROM jobs WHERE id IN (SELECT id FROM jobs ORDER BY updated DESC LIMIT -1 OFFSET 200)"
        )
        self.db.commit()
        self.jobs: dict[str, Job] = {}
        for row in self.db.execute(
            "SELECT id,operation,inputs,options,destination,state,outputs,error FROM jobs ORDER BY updated DESC LIMIT 30"
        ):
            paths = [Path(value) for value in json.loads(row[2])]
            if not paths:
                continue
            outputs = [Path(value) for value in json.loads(row[6])]
            state = "partial" if row[5] == "interrupted" and outputs else row[5]
            self.jobs[row[0]] = Job(
                row[0],
                row[1],
                paths,
                json.loads(row[3]),
                Path(row[4]) if row[4] else paths[0].parent,
                beside_sources=not bool(row[4]),
                state=state,
                progress=1 if state == "succeeded" else 0,
                message="Interrupted; retry explicitly" if state == "interrupted" else state,
                outputs=outputs,
                error=row[7],
            )
        self.pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="mandarin-job"
        )
        self.heavy = threading.Semaphore(1)

    def record(self, job: Job):
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    job.id,
                    job.operation,
                    json.dumps([str(p) for p in job.inputs]),
                    json.dumps(job.options),
                    "" if job.beside_sources else str(job.destination),
                    job.state,
                    json.dumps([str(p) for p in job.outputs]),
                    job.error,
                    time.time(),
                ),
            )
            self.db.commit()
        self.callback(job)

    def submit(
        self,
        paths: list[Path],
        operation: str,
        options: dict | None = None,
        destination: Path | None = None,
    ) -> Job:
        if not paths or len(paths) > 1000:
            raise ValueError("Select between one and 1,000 files.")
        if (
            sum(
                job.state in {"queued", "running", "validating", "publishing"}
                for job in self.jobs.values()
            )
            >= 32
        ):
            raise ValueError(
                "The queue is full. Wait for a conversion to finish before adding more."
            )
        normalized = [Path(p).absolute() for p in paths]
        for path in normalized:
            file_identity(path)
        clean = validate_options(operation, options or {})
        if not operation.startswith("convert:"):
            definition = BY_ID[operation]
            if len(normalized) < definition.minimum_inputs:
                raise ValueError(
                    f"{definition.name} needs at least {definition.minimum_inputs} files."
                )
        target = (destination or normalized[0].parent).resolve()
        if destination is None and not (operation in BY_ID and BY_ID[operation].aggregate):
            if any(not os.access(path.parent, os.W_OK) for path in normalized):
                raise ValueError("Choose a writable output folder for this selection.")
        if not target.is_dir() or not os.access(target, os.W_OK):
            raise ValueError("Choose a writable output folder.")
        job = Job(
            uuid.uuid4().hex,
            operation,
            normalized,
            clean,
            target,
            beside_sources=destination is None,
        )
        self.jobs[job.id] = job
        self.record(job)
        self.pool.submit(self._execute, job)
        return job

    def _worker(
        self,
        workspace: Path,
        request: dict,
        inputs: list[Path],
        job: Job | None = None,
        timeout: int = 900,
    ) -> dict:
        name = "request-" + uuid.uuid4().hex + ".json"
        request_path = workspace / name
        request_path.write_text(json.dumps(request, ensure_ascii=True), encoding="utf-8")
        command = sandbox_command(
            workspace,
            inputs,
            python_command() + ["-m", "mandarin.worker", str(request_path)],
            timeout,
        )
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=worker_environment(workspace),
            start_new_session=True,
            bufsize=0,
        )
        if job:
            job.process = process
        messages: queue.Queue = queue.Queue()
        errors = bytearray()

        def read_output():
            try:
                while True:
                    line = process.stdout.readline(4 * 1024 * 1024 + 1)
                    if not line:
                        break
                    if len(line) > 4 * 1024 * 1024:
                        messages.put(
                            {
                                "event": "error",
                                "message": "Worker response exceeded its limit.",
                            }
                        )
                        self._terminate(process)
                        break
                    try:
                        messages.put(json.loads(line))
                    except (ValueError, UnicodeError):
                        pass
            finally:
                messages.put(None)

        def read_errors():
            while block := process.stderr.read(8192):
                errors.extend(block)
                if len(errors) > 16384:
                    del errors[:-16384]

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        error_reader = threading.Thread(target=read_errors, daemon=True)
        error_reader.start()
        result = None
        failure = ""
        started = time.monotonic()
        try:
            done = False
            while not done:
                if job and job.cancel_event.is_set():
                    self._terminate(process)
                    raise Canceled()
                if time.monotonic() - started > timeout + 3:
                    self._terminate(process)
                    raise ValueError("The operation exceeded its time limit.")
                try:
                    event = messages.get(timeout=0.1)
                except queue.Empty:
                    continue
                if event is None:
                    done = True
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("event") == "result":
                    result = event
                elif event.get("event") == "error":
                    failure = str(event.get("message", "Worker failed"))[:4096]
                elif event.get("event") == "progress" and job:
                    job.progress = max(0, min(0.9, float(event.get("fraction", 0)) * 0.9))
                    job.message = str(event.get("message", "Processing"))[:512]
                    self.callback(job)
            code = process.wait(timeout=3)
            error_reader.join(timeout=1)
            if code or result is None:
                raise ValueError(
                    failure
                    or errors.decode("utf-8", "replace")[-2000:]
                    or "The worker stopped without producing a result."
                )
            return result
        finally:
            if process.poll() is None:
                self._terminate(process)
            process.stdout.close()
            process.stderr.close()
            if job:
                job.process = None

    @staticmethod
    def _terminate(process):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
        # The leader might exit before an orphan; always kill the held group too.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def inspect(self, paths: list[Path]) -> list[dict]:
        if len(paths) > 1000:
            raise ValueError("Select no more than 1,000 files.")
        for path in paths:
            file_identity(path)
        with tempfile.TemporaryDirectory(prefix="mandarin-probe-", dir=self.state_dir) as temporary:
            workspace = Path(temporary)
            result = self._worker(
                workspace,
                {"mode": "probe", "inputs": [str(p.absolute()) for p in paths]},
                paths,
                timeout=45,
            )
        return result["items"]

    def preview(
        self,
        path: Path,
        operation: str | None = None,
        options: dict | None = None,
        cancel: threading.Event | None = None,
    ) -> dict:
        with tempfile.TemporaryDirectory(
            prefix="mandarin-preview-", dir=self.state_dir
        ) as temporary:
            workspace = Path(temporary)
            context = Job(
                "preview",
                operation or "",
                [path],
                options or {},
                workspace,
                cancel_event=cancel or threading.Event(),
            )
            result = self._worker(
                workspace,
                {
                    "mode": "preview",
                    "inputs": [str(path.absolute())],
                    "operation": operation,
                    "options": options or {},
                },
                [path],
                job=context,
                timeout=30,
            )
            width, height = int(result["width"]), int(result["height"])
            if not (0 < width <= 640 and 0 < height <= 640):
                raise ValueError("Invalid preview dimensions.")
            data = (workspace / "preview.rgba").read_bytes()
            if len(data) != width * height * 4:
                raise ValueError("Invalid preview pixel buffer.")
            return {"width": width, "height": height, "data": data}

    def _execute(self, job: Job):
        workspace = None
        try:
            with self.heavy:
                if job.cancel_event.is_set():
                    raise Canceled()
                identities = [file_identity(p) for p in job.inputs]
                if any(p.is_dir() for p in job.inputs):
                    raise ValueError("Choose files for conversion. Folders support file actions.")
                size = sum(identity[2] for identity in identities)
                if shutil.disk_usage(job.destination).free < size * 2 + 16 * 1024 * 1024:
                    raise ValueError("There is not enough space in this output folder.")
                workspace = Path(
                    tempfile.mkdtemp(prefix=".mandarin-" + job.id + "-", dir=job.destination)
                )
                sources = []
                for index, path in enumerate(job.inputs):
                    if job.cancel_event.is_set():
                        raise Canceled()
                    suffix = (
                        ".tar.gz" if path.name.lower().endswith(".tar.gz") else path.suffix.lower()
                    )
                    safe = workspace / (f"input-{index:04}" + suffix)
                    with path.open("rb") as source, safe.open("xb") as target:
                        while block := source.read(1024 * 1024):
                            if job.cancel_event.is_set():
                                raise Canceled()
                            target.write(block)
                    if file_identity(path) != identities[index]:
                        raise ValueError(
                            "A source file changed while it was being read. Retry with a stable copy."
                        )
                    sources.append(safe)
                job.state = "running"
                job.message = "Converting"
                self.record(job)
                request = {
                    "mode": "execute",
                    "inputs": [str(p) for p in sources],
                    "names": [p.name for p in job.inputs],
                    "operation": job.operation,
                    "options": job.options,
                }
                result = self._worker(workspace, request, [], job)
                artifacts = result.get("artifacts", [])
                if not isinstance(artifacts, list) or not artifacts or len(artifacts) > 1000:
                    raise ValueError("Invalid output manifest.")
                output_base = workspace / "outputs"
                for artifact in artifacts:
                    if (
                        not isinstance(artifact, dict)
                        or not isinstance(artifact.get("path"), str)
                        or not isinstance(artifact.get("name"), str)
                    ):
                        raise ValueError("Invalid output entry.")
                    path = workspace / artifact["path"]
                    if not path.resolve().is_relative_to(output_base) or path.is_symlink():
                        raise ValueError("Unsafe output path.")
                    for member in [path] + list(path.rglob("*")) if path.is_dir() else [path]:
                        st = member.lstat()
                        if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)) or (
                            stat.S_ISREG(st.st_mode) and st.st_nlink != 1
                        ):
                            raise ValueError("Unsafe output artifact.")
                        os.chmod(member, 0o700 if stat.S_ISDIR(st.st_mode) else 0o600)
                        for attribute in os.listxattr(member):
                            os.removexattr(member, attribute)
                job.state = "validating"
                job.progress = 0.92
                job.message = "Checking the result"
                self.record(job)
                validation = self._worker(
                    workspace, {"mode": "validate", "artifacts": artifacts}, [], job
                )
                if job.operation.startswith("convert:"):
                    expected = job.operation.split(":", 1)[1]
                    if not validation.get("validated") or any(
                        row.get("format") != expected for row in validation["validated"]
                    ):
                        raise ValueError("The output content does not match the requested format.")
                if job.cancel_event.is_set():
                    raise Canceled()
                if any(file_identity(p) != identity for p, identity in zip(job.inputs, identities)):
                    raise ValueError(
                        "A source changed during processing. The original was preserved; retry with a stable copy."
                    )
                job.state = "publishing"
                job.message = "Saving complete output"
                self.record(job)
                for artifact in artifacts:
                    if job.cancel_event.is_set():
                        raise Canceled()
                    index = artifact.get("source_index", 0)
                    if (
                        isinstance(index, bool)
                        or not isinstance(index, int)
                        or not 0 <= index < len(job.inputs)
                    ):
                        raise ValueError("Invalid artifact source mapping.")
                    destination = (
                        job.inputs[index].parent.resolve()
                        if job.beside_sources
                        else job.destination
                    )
                    artifact_path = workspace / artifact["path"]
                    relocated = None
                    if artifact_path.stat().st_dev != destination.stat().st_dev:
                        relocated = Path(
                            tempfile.mkdtemp(prefix=".mandarin-publish-", dir=destination)
                        )
                        copied = relocated / artifact_path.name
                        if artifact_path.is_dir():
                            shutil.copytree(artifact_path, copied)
                        else:
                            shutil.copyfile(artifact_path, copied)
                        for record in validation["validated"]:
                            source = workspace / record["path"]
                            if source == artifact_path or source.is_relative_to(artifact_path):
                                output = (
                                    copied
                                    if source == artifact_path
                                    else copied / source.relative_to(artifact_path)
                                )
                                with output.open("rb") as handle:
                                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                                if digest != record["sha256"]:
                                    raise ValueError("The copied output failed verification.")
                        artifact_path = copied
                    try:
                        job.outputs.append(publish(artifact_path, destination, artifact["name"]))
                    finally:
                        if relocated:
                            shutil.rmtree(relocated, ignore_errors=True)
                    self.record(job)
                job.state = "succeeded"
                job.progress = 1
                job.message = "Ready"
                self.record(job)
        except Canceled:
            job.state = "partial" if job.outputs else "canceled"
            job.message = "Canceled"
            self.record(job)
        except Exception as exc:
            job.state = "partial" if job.outputs else "failed"
            job.error = str(exc)[:4096]
            job.message = "Could not complete"
            self.record(job)
        finally:
            if workspace:
                shutil.rmtree(workspace, ignore_errors=True)

    def cancel(self, job_id: str):
        job = self.jobs[job_id]
        job.cancel_event.set()

    def retry(self, job_id: str) -> Job:
        job = self.jobs[job_id]
        if job.state not in {"failed", "canceled", "interrupted"} or job.outputs:
            raise ValueError("Only failed or canceled jobs can be retried.")
        return self.submit(
            job.inputs,
            job.operation,
            job.options,
            None if job.beside_sources else job.destination,
        )

    def history(self) -> list[dict]:
        with self.lock:
            return [
                {
                    "id": row[0],
                    "operation": row[1],
                    "state": row[2],
                    "outputs": json.loads(row[3]),
                    "error": row[4],
                }
                for row in self.db.execute(
                    "SELECT id,operation,state,outputs,error FROM jobs ORDER BY updated DESC LIMIT 30"
                )
            ]

    def clear_history(self):
        with self.lock:
            self.db.execute(
                "DELETE FROM jobs WHERE state NOT IN ('queued','running','validating','publishing')"
            )
            self.db.commit()

    def close(self):
        for job in self.jobs.values():
            if job.state in {"queued", "running", "validating"}:
                job.cancel_event.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.db.close()
