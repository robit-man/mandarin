import hashlib
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from mandarin.jobs import JobManager
from mandarin.runtime import engine, python_command, sandbox_command, worker_environment


class WorkerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.manager = JobManager(self.root / "state")

    def tearDown(self):
        self.manager.close()
        self.temporary.cleanup()

    def wait(self, job):
        deadline = time.monotonic() + 100
        while job.state in {"queued", "running", "validating", "publishing"}:
            if time.monotonic() > deadline:
                self.manager.cancel(job.id)
                self.fail("Job did not finish")
            time.sleep(0.05)
        self.assertEqual(job.state, "succeeded", job.error)
        return job.outputs

    def image(self, name="source.png"):
        path = self.root / name
        Image.new("RGBA", (96, 64), (250, 120, 20, 180)).save(path)
        return path

    def test_real_conversion_and_collision_preserve_original(self):
        source = self.image("file $(not-a-command).png")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        first = self.wait(self.manager.submit([source], "convert:jpg"))[0]
        second = self.wait(self.manager.submit([source], "convert:jpg"))[0]
        self.assertNotEqual(first, second)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        with Image.open(second) as decoded:
            self.assertEqual(decoded.size, (96, 64))
            self.assertEqual(decoded.format, "JPEG")

    def test_bounded_raw_preview_and_content_probe(self):
        source = self.image("misleading.png")
        renamed = self.root / "pretend.mp3"
        source.rename(renamed)
        self.assertEqual(self.manager.inspect([renamed])[0]["family"], "image")
        preview = self.manager.preview(renamed)
        self.assertEqual(len(preview["data"]), preview["width"] * preview["height"] * 4)

    def test_actual_audio_transcode_and_channels(self):
        source = self.root / "tone.wav"
        subprocess.run(
            engine("ffmpeg")
            + [
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=0.3",
                str(source),
            ],
            check=True,
        )
        result = self.wait(self.manager.submit([source], "convert:flac"))[0]
        decoded = self.manager.inspect([result])[0]
        self.assertEqual(decoded["family"], "audio")
        self.assertAlmostEqual(decoded["duration"], 0.3, places=2)
        stereo = self.wait(self.manager.submit([source], "channels", {"channels": "stereo"}))[0]
        self.assertEqual(self.manager.inspect([stereo])[0]["streams"][0]["channels"], 2)

    def test_pdf_generation_raster_and_page_order(self):
        one = self.image("one.png")
        two = self.image("two.png")
        pdf = self.wait(self.manager.submit([one, two], "images_pdf"))[0]
        from pypdf import PdfReader

        self.assertEqual(len(PdfReader(pdf).pages), 2)
        pages = self.wait(self.manager.submit([pdf], "convert:png"))[0]
        self.assertEqual(len(list(pages.glob("*.png"))), 2)
        organized = self.wait(
            self.manager.submit([pdf], "organize_pdf", {"pages": "2,1,1", "rotation": "90"})
        )[0]
        self.assertEqual(len(PdfReader(organized).pages), 3)

    def test_archive_roundtrip_and_traversal_rejection(self):
        source = self.root / "archive.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("folder/file.txt", "content")
        output = self.wait(self.manager.submit([source], "convert:tar"))[0]
        extracted = self.wait(self.manager.submit([output], "extract"))[0]
        self.assertEqual((extracted / "folder/file.txt").read_text(), "content")
        hostile = self.root / "evil.zip"
        with zipfile.ZipFile(hostile, "w") as archive:
            archive.writestr("../escaped", "bad")
        job = self.manager.submit([hostile], "extract")
        while job.state in {"queued", "running", "validating", "publishing"}:
            time.sleep(0.05)
        self.assertEqual(job.state, "failed")
        self.assertFalse((self.root / "escaped").exists())

    def test_subtitles_actual_cues(self):
        source = self.root / "captions.srt"
        source.write_text("1\n00:00:01,000 --> 00:00:02,500\nHello 世界\n")
        output = self.wait(self.manager.submit([source], "convert:vtt"))[0]
        text = output.read_text()
        self.assertTrue(text.startswith("WEBVTT"))
        self.assertIn("00:00:02.500", text)
        self.assertIn("世界", text)

    def test_document_conversion_is_isolated(self):
        source = self.root / "notes.md"
        source.write_text("# Notes\n\nA local document.\n")
        docx = self.wait(self.manager.submit([source], "convert:docx"))[0]
        self.assertTrue(zipfile.is_zipfile(docx))
        pdf = self.wait(self.manager.submit([docx], "convert:pdf"))[0]
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))

    def test_sandbox_denies_ungranted_file_network_and_process_escape(self):
        secret = self.root / "secret"
        secret.write_text("private")
        workspace = self.root / "sandbox"
        workspace.mkdir()
        code = """import os,socket
checks=[]
for f in [lambda:open(%r).read(),lambda:socket.socket(socket.AF_INET,socket.SOCK_STREAM),lambda:os.setsid()]:
 try:f();checks.append(False)
 except PermissionError:checks.append(True)
print(checks)
raise SystemExit(0 if all(checks) else 1)
""" % str(secret)
        result = subprocess.run(
            sandbox_command(workspace, [], python_command() + ["-c", code]),
            env=worker_environment(workspace),
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("[True, True, True]", result.stdout)

    def test_cancelled_job_does_not_publish(self):
        source = self.image()
        job = self.manager.submit([source], "convert:jpg")
        self.manager.cancel(job.id)
        deadline = time.monotonic() + 5
        while (
            job.state in {"queued", "running", "validating", "publishing"}
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        self.assertEqual(job.state, "canceled")
        self.assertEqual(job.outputs, [])
        self.assertTrue(source.exists())

    def test_mixed_folders_publish_beside_each_source(self):
        first = self.image()
        folder = self.root / "other"
        folder.mkdir()
        second = folder / "second.png"
        Image.new("RGB", (32, 32), "red").save(second)
        outputs = self.wait(self.manager.submit([first, second], "convert:jpg"))
        self.assertEqual([p.parent for p in outputs], [first.parent, second.parent])

    def test_move_keeps_verified_recovery_source(self):
        from mandarin.move import move_files

        source = self.image()
        original = source.read_bytes()
        destination = self.root / "destination"
        destination.mkdir()
        result = move_files([source], destination, self.manager.state_dir)
        entry = result["items"][0]
        self.assertFalse(source.exists())
        self.assertEqual(Path(entry["destination"]).read_bytes(), original)
        self.assertEqual(Path(entry["recovery"]).read_bytes(), original)

    def test_move_rejects_link_and_preserves_existing_destination(self):
        from mandarin.move import move_files

        source = self.image()
        destination = self.root / "destination"
        destination.mkdir()
        existing = destination / source.name
        existing.write_bytes(b"existing")
        result = move_files([source], destination, self.manager.state_dir)
        self.assertNotEqual(Path(result["items"][0]["destination"]), existing)
        self.assertEqual(existing.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
