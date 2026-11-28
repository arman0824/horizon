import io
import json
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools import lab, launcher


class ClassifyMinecraftTest(unittest.TestCase):
    def test_a_plain_game_folder_is_minecraft(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(launcher.classify_minecraft(folder), "minecraft")
            (folder / "versions" / lab.VERSION).mkdir(parents=True)
            self.assertTrue(launcher.has_version(folder, lab.VERSION))

    def test_a_prism_root_is_prism(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "instances").mkdir()
            self.assertEqual(launcher.classify_minecraft(folder), "prism")

    def test_a_prism_instance_keeps_the_game_one_level_down(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "minecraft" / "versions" / lab.VERSION).mkdir(parents=True)
            self.assertEqual(launcher.classify_minecraft(folder), "prism")
            self.assertTrue(launcher.has_version(folder, lab.VERSION))

    def test_a_folder_without_the_version_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertFalse(launcher.has_version(folder, lab.VERSION))


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

    def test_the_low_memory_build_uses_one_job(self):
        with mock.patch.dict("os.environ", {"HORIZON_BUILD_JOBS": "8"}):
            self.assertEqual(launcher.build_jobs(low_memory=True), 1)
            command = launcher.build_command(low_memory=True)
            self.assertEqual(command[command.index("--jobs") + 1], "1")

    def test_the_low_memory_environment_cuts_compiler_memory(self):
        with mock.patch.dict("os.environ", {"RUSTFLAGS": "-Zthreads=8 -C target-cpu=native"}):
            env = launcher.low_memory_environment()
        self.assertEqual(env["HORIZON_BUILD_JOBS"], "1")
        self.assertIn("-Zthreads=1", env["RUSTFLAGS"])
        self.assertNotIn("-Zthreads=8", env["RUSTFLAGS"])
        self.assertIn("-C target-cpu=native", env["RUSTFLAGS"])
        self.assertEqual(env["CARGO_PROFILE_FAST_OPT_LEVEL"], "1")
        self.assertEqual(env["CARGO_PROFILE_FAST_INCREMENTAL"], "false")


class PrebuiltTest(unittest.TestCase):
    def test_the_asset_is_the_linux_build(self):
        with mock.patch.object(launcher.sys, "platform", "linux"), \
                mock.patch.object(launcher.platform, "machine", lambda: "x86_64"):
            self.assertEqual(launcher.prebuilt_asset(), launcher.PREBUILT_ASSET)
        with mock.patch.object(launcher.sys, "platform", "darwin"), \
                mock.patch.object(launcher.platform, "machine", lambda: "arm64"):
            self.assertIsNone(launcher.prebuilt_asset())

    def test_the_checksum_comes_from_the_sums_file(self):
        digest = "a" * 64
        sums = f"{'b' * 64}  other.tar.gz\n{digest}  *{launcher.PREBUILT_ASSET}\n"
        self.assertEqual(launcher.checksum_for(sums, launcher.PREBUILT_ASSET), digest)
        with self.assertRaises(ValueError):
            launcher.checksum_for(sums, "missing.tar.gz")
        with self.assertRaises(ValueError):
            launcher.checksum_for(f"not-a-checksum  {launcher.PREBUILT_ASSET}", launcher.PREBUILT_ASSET)

    def test_installing_takes_the_binaries_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = self.archive(
                tmp,
                {
                    "horizon-linux-x86_64/target/fast/horizon-client": b"game",
                    "horizon-linux-x86_64/target/fast/horizon-prepare": b"prepare",
                    "horizon-linux-x86_64/target/fast/horizon-ctl": b"ctl",
                    "horizon-linux-x86_64/README.md": b"readme",
                },
            )
            root = tmp / "root"
            installed = launcher.install_prebuilt(archive, root)
            self.assertEqual(
                {path.name for path in installed},
                {"horizon-client", "horizon-prepare", "horizon-ctl"},
            )
            binary = root / "target" / "fast" / "horizon-client"
            self.assertEqual(binary.read_bytes(), b"game")
            self.assertTrue(os.access(binary, os.X_OK))
            self.assertFalse((root / "target" / "fast" / "README.md").exists())

    def test_an_archive_with_a_path_outside_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = self.archive(
                tmp,
                {
                    "../escaped": b"no",
                    "horizon-linux-x86_64/target/fast/horizon-client": b"game",
                    "horizon-linux-x86_64/target/fast/horizon-prepare": b"prepare",
                },
            )
            with self.assertRaises(ValueError):
                launcher.install_prebuilt(archive, tmp / "root")
            self.assertFalse((tmp / "escaped").exists())

    def test_a_partial_archive_leaves_the_installed_game_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = self.archive(
                tmp, {"horizon-linux-x86_64/target/fast/horizon-prepare": b"prepare"}
            )
            fast = tmp / "root" / "target" / "fast"
            fast.mkdir(parents=True)
            (fast / "horizon-client").write_bytes(b"old")
            with self.assertRaises(ValueError):
                launcher.install_prebuilt(archive, tmp / "root")
            self.assertEqual((fast / "horizon-client").read_bytes(), b"old")
            self.assertFalse((fast / "horizon-prepare").exists())
            self.assertEqual(list(fast.glob("*.part")), [])

    @staticmethod
    def archive(directory: Path, entries: dict[str, bytes]) -> Path:
        path = directory / "release.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            for name, data in entries.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(data))
        return path


class SettingsTest(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            with mock.patch.object(launcher, "settings_path", lambda: path):
                launcher.save_settings(
                    {"sounds": False, "low_memory": True, "game_dir": "/tmp/w", "extra_args": "x"}
                )
                loaded = launcher.load_settings()
            self.assertEqual(loaded["sounds"], False)
            self.assertEqual(loaded["low_memory"], True)
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


class ModsAndPacksTest(unittest.TestCase):
    def hmod(self, folder: Path, manifest: str, name: str = "ruby.hmod") -> Path:
        path = folder / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("horizon-mod.toml", manifest)
        return path

    def test_reads_a_content_mod_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = self.hmod(
                Path(tmp),
                'id = "ruby"\nname = "Ruby Blocks"\nversion = "1.2.3"\napi = "0.2"\n'
                'capabilities = ["registries"]\n\n[content]\n',
            )
            info = launcher.read_mod(mod)
            self.assertEqual(info["id"], "ruby")
            self.assertEqual(info["name"], "Ruby Blocks")
            self.assertEqual(info["version"], "1.2.3")
            self.assertFalse(info["native"])

    def test_a_native_mod_is_recognised(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = self.hmod(
                Path(tmp), 'id = "fast"\nname = "Fast"\nversion = "1.0.0"\n\n[native]\ngame = "26.3"\n'
            )
            self.assertTrue(launcher.read_mod(mod)["native"])

    def test_a_zip_without_a_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not-a-mod.hmod"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("readme.txt", "hello")
            with self.assertRaises(ValueError):
                launcher.read_mod(path)

    def test_installing_a_mod_copies_it_and_turns_it_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "game"
            mod = self.hmod(Path(tmp), 'id = "ruby"\nname = "Ruby"\nversion = "1.0.0"\n')
            launcher.install_mod(mod, game)
            self.assertTrue((game / "horizon-mods" / "ruby.hmod").is_file())
            self.assertIn("mod.ruby:true", (game / "horizon-mods.txt").read_text())

    def test_a_folder_mod_is_copied_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "ruby"
            (source / "assets").mkdir(parents=True)
            (source / "horizon-mod.toml").write_text('id = "ruby"\nname = "Ruby"\nversion = "1"\n')
            (source / "assets" / "a.txt").write_text("x")
            game = Path(tmp) / "game"
            launcher.install_mod(source, game)
            self.assertTrue((game / "horizon-mods" / "ruby" / "assets" / "a.txt").is_file())

    def test_turning_a_mod_off_keeps_the_other_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            (game / "horizon-mods.txt").write_text(
                "mod.other:true\nkey.ruby.jump:key.keyboard.space\n"
            )
            launcher.set_mod_enabled(game, "ruby", True)
            launcher.set_mod_enabled(game, "ruby", False)
            text = (game / "horizon-mods.txt").read_text()
            self.assertIn("mod.other:true", text)
            self.assertIn("key.ruby.jump:key.keyboard.space", text)
            self.assertIn("mod.ruby:false", text)
            self.assertNotIn("mod.ruby:true", text)

    def test_installed_mods_report_their_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "game"
            mod = self.hmod(Path(tmp), 'id = "ruby"\nname = "Ruby"\nversion = "1.0.0"\n')
            launcher.install_mod(mod, game)
            self.assertEqual(
                [(m["id"], m["on"]) for m in launcher.installed_mods(game)], [("ruby", True)]
            )
            launcher.set_mod_enabled(game, "ruby", False)
            self.assertEqual(
                [(m["id"], m["on"]) for m in launcher.installed_mods(game)], [("ruby", False)]
            )

    def test_a_classic_shader_pack_is_a_zip_with_a_shaders_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "nice.zip"
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("shaders/final.vsh", "void main() {}")
            self.assertTrue(launcher.is_shader_pack(pack))
            self.assertFalse(launcher.is_resource_pack(pack))
            game = Path(tmp) / "game"
            destination = launcher.install_pack(pack, game, "shader")
            self.assertEqual(destination, game / "shaderpacks" / "nice.zip")
            self.assertTrue(destination.is_file())

    def test_a_horizon_pack_is_a_zip_with_its_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "soft.hshader"
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("horizon-shaders.toml", 'id = "soft"\nname = "Soft"\n')
            self.assertTrue(launcher.is_shader_pack(pack))

    def test_a_resource_pack_needs_pack_mcmeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "faithful.zip"
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("pack.mcmeta", '{"pack": {"pack_format": 1}}')
            self.assertTrue(launcher.is_resource_pack(pack))
            game = Path(tmp) / "game"
            self.assertTrue(launcher.install_pack(pack, game, "resource").is_file())

    def test_a_shader_pack_is_refused_as_a_resource_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "nice.zip"
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("shaders/final.vsh", "void main() {}")
            with self.assertRaises(ValueError):
                launcher.install_pack(pack, Path(tmp) / "game", "resource")


if __name__ == "__main__":
    unittest.main()
