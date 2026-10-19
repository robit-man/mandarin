import json
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from PIL import Image
from mandarin.jobs import JobManager
from mandarin.operations import BY_ID
from mandarin.runtime import engine


class ToolSmokeTests(unittest.TestCase):
    def test_actual_tool_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = JobManager(root / "state")
            image = root / "image.png"
            Image.new("RGB", (96, 64), "orange").save(image)
            image2 = root / "second.png"
            Image.new("RGB", (96, 64), "green").save(image2)
            audio = root / "tone.wav"
            subprocess.run(
                engine("ffmpeg")
                + ["-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(audio)],
                check=True,
            )
            video = root / "clip.mp4"
            subprocess.run(
                engine("ffmpeg")
                + [
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=orange:s=96x64:d=1",
                    "-i",
                    str(audio),
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    str(video),
                ],
                check=True,
            )
            archive = root / "files.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("note.txt", "Local file")
            from reportlab.pdfgen import canvas

            pdf = root / "pages.pdf"
            document = canvas.Canvas(str(pdf))
            document.drawString(20, 50, "Mandarin")
            document.showPage()
            document.drawString(20, 50, "Second page")
            document.save()
            import cv2

            qr = root / "code.png"
            encoded = cv2.QRCodeEncoder_create().encode("mandarin-local-test")
            encoded = cv2.copyMakeBorder(encoded, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
            cv2.imwrite(
                str(qr), cv2.resize(encoded, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
            )
            cases = [
                ("compress", [image], {"target_kb": 100}),
                ("metadata", [image], {"mode": "inspect"}),
                ("crop_image", [image], {"x": 2, "y": 2, "width": 40, "height": 30}),
                ("resize", [image], {"width": 48, "height": 32}),
                ("edit_image", [image], {"brightness": 1.2}),
                ("annotate", [image], {"text": "Local", "font_size": 16}),
                ("background", [image], {}),
                ("collage", [image, image2], {"cell": 96}),
                ("images_pdf", [image, image2], {}),
                ("trim_video", [video], {"start": 0.1, "end": 0.7}),
                ("crop_video", [video], {"width": 48, "height": 32}),
                ("speed", [video], {"speed": 2}),
                ("mute", [video], {}),
                ("snapshot", [video], {"start": 0.2}),
                ("split_video", [video], {"parts": 2}),
                ("join", [video, video], {}),
                ("normalize", [audio], {}),
                ("trim_audio", [audio], {"start": 0.1, "end": 0.7}),
                ("channels", [audio], {"channels": "stereo"}),
                ("visualizer", [audio], {"width": 96, "height": 64, "color": "#ee3300"}),
                ("bleep", [audio], {"start": 0.1, "end": 0.4}),
                ("redact_image", [image], {"width": 20, "height": 20}),
                ("redact_video", [video], {"width": 20, "height": 20, "start": 0.1, "end": 0.5}),
                ("merge_pdf", [pdf, pdf], {}),
                ("split_pdf", [pdf], {}),
                ("organize_pdf", [pdf], {"pages": "2,1"}),
                ("extract", [archive], {}),
                ("qr", [qr], {}),
                ("metadata", [audio], {"mode": "remove"}),
                ("metadata", [pdf], {"mode": "remove"}),
                ("redact_image", [image], {"detect": "faces"}),
                ("redact_image", [image], {"detect": "text"}),
            ]
            results = []
            try:
                for operation, paths, options in cases:
                    with self.subTest(operation=operation, options=options):
                        job = manager.submit(paths, operation, options)
                        deadline = time.monotonic() + 60
                        while (
                            job.state in {"queued", "running", "validating", "publishing"}
                            and time.monotonic() < deadline
                        ):
                            time.sleep(0.05)
                        if job.state in {"queued", "running", "validating", "publishing"}:
                            manager.cancel(job.id)
                        results.append(
                            {
                                "operation": operation,
                                "options": options,
                                "status": job.state,
                                "error": job.error,
                            }
                        )
                        self.assertEqual(job.state, "succeeded", job.error)
                        self.assertTrue(all(path.exists() for path in job.outputs))
                        if operation == "qr":
                            self.assertIn("mandarin-local-test", job.outputs[0].read_text())
                Path("build").mkdir(exist_ok=True)
                Path("build/tool-report.json").write_text(
                    json.dumps({"cases": results, "operations": len(BY_ID)}, indent=2)
                )
            finally:
                manager.close()


if __name__ == "__main__":
    unittest.main()
