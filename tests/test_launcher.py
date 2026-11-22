import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import launcher


class ClassifyMinecraftTest(unittest.TestCase):
    def test_a_plain_game_folder_is_minecraft(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(launcher.classify_minecraft(folder), "minecraft")
            (folder / "versions" / "26.3").mkdir(parents=True)
            self.assertTrue(launcher.has_version(folder, "26.3"))

    def test_a_prism_root_is_prism(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "instances").mkdir()
            self.assertEqual(launcher.classify_minecraft(folder), "prism")

    def test_a_prism_instance_keeps_the_game_one_level_down(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "minecraft" / "versions" / "26.3").mkdir(parents=True)
            self.assertEqual(launcher.classify_minecraft(folder), "prism")
            self.assertTrue(launcher.has_version(folder, "26.3"))

    def test_a_folder_without_the_version_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertFalse(launcher.has_version(folder, "26.3"))


class CommandTest(unittest.TestCase):
    def test_preparing_copies_the_sounds_unless_asked_not_to(self):
        on = launcher.prepare_command(("minecraft", "/mc"), Path("/jars/server.jar"), True)
        self.assertNotIn("--no-sounds", on)
        self.assertEqual(on[on.index("--server-jar") + 1], "/jars/server.jar")
        self.assertEqual(on[on.index("--minecraft-dir") + 1], "/mc")
        self.assertEqual(on[on.index("--output") + 1], str(launcher.resources_dir()))

        off = launcher.prepare_command(None, None, False)
        self.assertIn("--no-sounds", off)
        self.assertNotIn("--server-jar", off)
        self.assertNotIn("--minecraft-dir", off)

    def test_a_prism_folder_is_passed_as_a_prism_root(self):
        command = launcher.prepare_command(("prism", "/prism"), None, True)
        self.assertEqual(command[command.index("--prism-dir") + 1], "/prism")
        self.assertNotIn("--minecraft-dir", command)

    def test_the_game_gets_the_prepared_folder_and_the_game_folder(self):
        command = launcher.game_command(Path("/worlds"))
        self.assertEqual(command[command.index("--resources") + 1], str(launcher.resources_dir()))
        self.assertEqual(command[command.index("--game-dir") + 1], "/worlds")
        self.assertEqual(command[command.index("--home") + 1], "/worlds")
        self.assertNotIn("--session-file", command)

    def test_extra_arguments_are_appended_verbatim(self):
        command = launcher.game_command(Path("/worlds"), ["--creative", "--seed", "7"])
        self.assertEqual(command[-3:], ["--creative", "--seed", "7"])

    def test_split_extra_arguments_handles_quoting(self):
        self.assertEqual(launcher.split_extra_arguments(""), [])
        self.assertEqual(launcher.split_extra_arguments("a  b"), ["a", "b"])
        self.assertEqual(launcher.split_extra_arguments('--name "New World"'), ["--name", "New World"])

    def test_needs_version_json_matches_the_preparer_s_message(self):
        self.assertTrue(
            launcher.needs_version_json(
                ["foo", "x.json is not a 26.3 version file Horizon knows (sha1 abc): your launcher"]
            )
        )
        self.assertFalse(launcher.needs_version_json(["nothing relevant here"]))


class BuildTest(unittest.TestCase):
    def test_the_build_caps_parallel_jobs_for_memory(self):
        command = launcher.build_command()
        self.assertIn("--jobs", command)
        jobs = int(command[command.index("--jobs") + 1])
        self.assertGreaterEqual(jobs, 1)
        self.assertLessEqual(jobs, 8)
        self.assertIn("horizon-game", command)
        self.assertIn("horizon-prepare", command)

    def test_the_build_jobs_can_be_lowered(self):
        with mock.patch.dict("os.environ", {"HORIZON_BUILD_JOBS": "3"}):
            self.assertEqual(launcher.build_jobs(), 3)
            command = launcher.build_command()
            self.assertEqual(command[command.index("--jobs") + 1], "3")

    def test_a_bad_build_jobs_value_falls_back(self):
        with mock.patch.dict("os.environ", {"HORIZON_BUILD_JOBS": "nonsense"}):
            self.assertGreaterEqual(launcher.build_jobs(), 1)

    def test_a_small_machine_builds_with_fewer_jobs(self):
        with mock.patch.dict("os.environ", {"HORIZON_BUILD_JOBS": ""}), \
                mock.patch.object(launcher, "total_memory_gb", lambda: 8.0), \
                mock.patch.object(launcher.os, "cpu_count", lambda: 16):
            self.assertEqual(launcher.build_jobs(), 4)


class SettingsTest(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            with mock.patch.object(launcher, "settings_path", lambda: path):
                launcher.save_settings({"sounds": False, "game_dir": "/tmp/w", "extra_args": "x"})
                loaded = launcher.load_settings()
            self.assertEqual(loaded["sounds"], False)
            self.assertEqual(loaded["game_dir"], "/tmp/w")
            self.assertEqual(loaded["extra_args"], "x")

    def test_load_settings_rejects_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("not json")
            with mock.patch.object(launcher, "settings_path", lambda: path):
                self.assertEqual(launcher.load_settings(), {})


class DownloadTest(unittest.TestCase):
    def test_cached_server_jar_download_returns_the_pinned_sha(self):
        # The cached manifest (if present) must agree with the pin.
        cached = launcher.ROOT / ".local" / "minecraft" / launcher.pins()["version"] / "manifest.json"
        if not cached.is_file():
            self.skipTest("no cached version file")
        url, want, size = launcher.server_download(launcher.pins()["version"])
        self.assertEqual(want, launcher.pins()["server_sha1"])
        self.assertTrue(url.startswith("http"))
        self.assertGreater(size, 0)


class SelfTestTest(unittest.TestCase):
    def test_self_test_json_reports_the_pinned_version(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(launcher.ROOT / "tools" / "launcher.py"), "--self-test", "--json"],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["version"], launcher.pins()["version"])
        self.assertIn("game_built", data)
        self.assertIn("prepare_built", data)


if __name__ == "__main__":
    unittest.main()
