import os
import tempfile
import unittest
from pathlib import Path

from mandarin.capabilities import MenuItem, common_targets
from mandarin.files import parse_uris, publish
from mandarin.operations import validate_options
from mandarin.radial import RadialState


class FilesystemTests(unittest.TestCase):
    def test_uri_list_preserves_names_and_rejects_remote(self):
        self.assertEqual(
            parse_uris(b"# note\r\nfile:///tmp/a%20%24%28b%29.png\r\n"),
            [Path("/tmp/a $(b).png")],
        )
        self.assertEqual(os.fsencode(parse_uris(b"file:///tmp/%ff.png")[0]), b"/tmp/\xff.png")
        for value in [
            "https://example.com/a.png",
            "file://server/path",
            "file:///tmp/a%00.png",
        ]:
            with self.assertRaises(ValueError):
                parse_uris(value)

    def test_publication_never_clobbers_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "photo.jpg"
            original.write_bytes(b"original")
            staging = root / "stage"
            staging.write_bytes(b"new")
            output = publish(staging, root, "photo.jpg")
            self.assertEqual(output.name, "photo (2).jpg")
            self.assertEqual(original.read_bytes(), b"original")
            self.assertEqual(output.read_bytes(), b"new")

    def test_publication_rejects_manifest_path_and_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "stage"
            staging.write_bytes(b"test")
            with self.assertRaises(ValueError):
                publish(staging, root, "../escape")
            link = root / "link"
            link.symlink_to(staging)
            with self.assertRaises(ValueError):
                publish(link, root, "copy")

    def test_directory_publication_reports_actual_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / "stage"
            staged.mkdir()
            (staged / "file.txt").write_text("complete")
            target = root / "destination"
            target.mkdir()
            result = publish(staged, target, "pages")
            self.assertEqual(result, target / "pages")
            self.assertEqual((result / "file.txt").read_text(), "complete")


class ContextTests(unittest.TestCase):
    def test_heterogeneous_images_intersect_but_media_does_not(self):
        engines = {"convert": True, "ffmpeg": True}
        png = {"family": "image", "format": "png"}
        heic = {"family": "image", "format": "heic"}
        mp3 = {"family": "audio", "format": "mp3"}
        self.assertIn("jpg", common_targets([png, heic], engines))
        self.assertNotIn("png", common_targets([png, heic], engines))
        self.assertEqual(common_targets([png, mp3], engines), [])
        self.assertEqual(common_targets([png], {}), [])

    def test_no_pages_writer_is_advertised(self):
        choices = common_targets(
            [{"family": "document", "format": "docx"}],
            {"soffice": True, "pandoc": True},
        )
        self.assertNotIn("pages", choices)

    def test_options_reject_unknown_and_invalid_intervals(self):
        with self.assertRaises(ValueError):
            validate_options("trim_video", {"start": 5, "end": 3})
        with self.assertRaises(ValueError):
            validate_options("crop_image", {"shell": "rm"})
        with self.assertRaises(ValueError):
            validate_options("speed", {"speed": float("nan")})
        self.assertEqual(validate_options("speed", {})["speed"], 2)


class RadialTests(unittest.TestCase):
    def tree(self):
        return [
            MenuItem(
                "category",
                "Convert",
                children=[MenuItem("deeper", "Images", children=[MenuItem("convert:jpg", "JPEG")])],
            )
        ]

    def test_three_levels_and_back(self):
        state = RadialState(self.tree())
        self.assertIsNone(state.choose(0))
        self.assertEqual(len(state.stack), 1)
        self.assertIsNone(state.choose(1))
        self.assertEqual(len(state.stack), 2)
        self.assertEqual(state.choose(1).id, "convert:jpg")
        state.choose(0)
        self.assertEqual(len(state.stack), 1)

    def test_stationary_child_never_executes_on_release(self):
        state = RadialState(self.tree())
        state.enter(0, 100, 50, now=0)
        state.enter(0, 100, 50, now=0.3)
        self.assertEqual(len(state.stack), 1)
        state.enter(1, 100, 50, now=0.4)
        self.assertIsNone(state.release(1))
        self.assertEqual(len(state.stack), 1)
        state.enter(1, 110, 50, now=0.5)
        self.assertTrue(state.armed)

    def test_deadzone_and_outer_bounds(self):
        state = RadialState(self.tree())
        self.assertIsNone(state.hit(200, 200, 200, 200))
        self.assertIsNone(state.hit(600, 200, 200, 200))
        self.assertEqual(state.hit(200, 70, 200, 200), 0)


if __name__ == "__main__":
    unittest.main()
