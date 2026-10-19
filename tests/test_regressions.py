import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from mandarin.jobs import JobManager
from mandarin.runtime import python_command, sandbox_command, worker_environment


class RegressionTests(unittest.TestCase):
    def test_all_image_frames_survive_conversion_and_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "two-pages.tiff"
            Image.new("RGB", (40, 30), "red").save(
                source, save_all=True, append_images=[Image.new("RGB", (40, 30), "blue")]
            )
            manager = JobManager(root / "state")
            try:
                self.assertEqual(manager.inspect([source])[0]["frames"], 2)
                for target in ["png", "pdf"]:
                    job = manager.submit([source], "convert:" + target)
                    deadline = time.monotonic() + 30
                    while job.state in {"queued", "running", "validating", "publishing"}:
                        if time.monotonic() > deadline:
                            manager.cancel(job.id)
                            self.fail("Frame conversion timed out")
                        time.sleep(0.05)
                    self.assertEqual(job.state, "succeeded", job.error)
                    if target == "png":
                        frames = sorted(job.outputs[0].glob("*.png"))
                        self.assertEqual(len(frames), 2)
                        self.assertNotEqual(
                            Image.open(frames[0]).convert("RGB").getpixel((0, 0)),
                            Image.open(frames[1]).convert("RGB").getpixel((0, 0)),
                        )
                    else:
                        from pypdf import PdfReader

                        self.assertEqual(len(PdfReader(job.outputs[0]).pages), 2)
            finally:
                manager.close()

    def test_broker_crash_kills_confined_descendants(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "job"
            workspace.mkdir()
            code = (
                "import subprocess,time,pathlib; "
                "p=subprocess.Popen("
                + repr(python_command() + ["-c", "import time; time.sleep(30)"])
                + "); "
                "pathlib.Path('ready.json').write_text(__import__('json').dumps([__import__('os').getpid(),p.pid])); time.sleep(30)"
            )
            command = sandbox_command(workspace, [], python_command() + ["-c", code])
            broker_code = (
                "import subprocess,time,pathlib,json; "
                "p=subprocess.Popen("
                + repr(command)
                + ",env="
                + repr(worker_environment(workspace))
                + ",start_new_session=True); "
                "pathlib.Path("
                + repr(str(root / "supervisor"))
                + ").write_text(str(p.pid)); time.sleep(30)"
            )
            broker = subprocess.Popen(python_command() + ["-c", broker_code])
            supervisor = None
            try:
                deadline = time.monotonic() + 8
                while not (workspace / "ready.json").exists():
                    if time.monotonic() > deadline:
                        self.fail("Confined descendants did not start")
                    time.sleep(0.05)
                supervisor = int((root / "supervisor").read_text())
                processes = [supervisor] + json.loads((workspace / "ready.json").read_text())
                broker.kill()
                broker.wait(timeout=3)

                def live(pid):
                    try:
                        return (
                            Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
                            != "Z"
                        )
                    except (FileNotFoundError, ProcessLookupError):
                        return False

                deadline = time.monotonic() + 3
                while any(live(pid) for pid in processes) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertFalse(
                    any(live(pid) for pid in processes), "A converter outlived its broker"
                )
            finally:
                if broker.poll() is None:
                    broker.kill()
                    broker.wait(timeout=3)
                if supervisor:
                    try:
                        os.killpg(supervisor, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
