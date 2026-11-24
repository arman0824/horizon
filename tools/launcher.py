#!/usr/bin/env python3
"""Horizon's launcher: pick your game files, press Play.

It performs the README's steps for you — find the installed Minecraft, fetch the matching
server jar from Mojang when it is not on this machine, build and prepare the game (the sounds
are part of preparing), then start it — with no account and no sign-in anywhere.

    tools/launcher.sh                       the window (finds a Python that has Tk)
    python3 tools/launcher.py --self-test   what it found, without a window
    python3 tools/launcher.py --download-prebuilt   install the release's programs, no build

Everything it downloads is checked against the SHA-1 pinned in research-lock.json. Resources
always live in this checkout (`.local/horizon-client/<version>`); the "Worlds & settings"
folder holds saves, options.txt and logs, so they survive rebuilds.

The window, the steps and the settings are importable (`from tools import launcher`) so the
tests can drive them without a display; `--smoke-test`, `--smoke-prepare` and `--smoke-play`
drive the real thing for a manual check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

try:  # The window needs Tk; --self-test and the tests work without it.
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, messagebox, ttk
except Exception:  # pragma: no cover - depends on the machine
    tk = None
    tkfont = None
    filedialog = messagebox = ttk = None

ROOT = Path(__file__).resolve().parents[1]
GAME_BIN = ROOT / "target" / "fast" / "horizon-client"
PREPARE_BIN = ROOT / "target" / "fast" / "horizon-prepare"
DEFAULT_GAME_DIR = Path.home() / "horizon-game"
RESOURCES_MARK = "horizon-resources.json"
SOUNDS_MARK = "assets/minecraft/sounds.json"
VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# The fork's own release: prebuilt programs for machines that should not compile Horizon.
RELEASE_REPO = "arman0824/horizon"
PREBUILT_ASSET = "horizon-linux-x86_64.tar.gz"
SHA256SUMS_ASSET = "SHA256SUMS"
PREBUILT_BINARIES = ("horizon-client", "horizon-prepare", "horizon-ctl")
USER_AGENT = "horizon-launcher"


# --------------------------------------------------------------------------- what is here


def pins() -> dict:
    """The Minecraft version and file checksums this checkout is pinned to."""
    with open(ROOT / "research-lock.json", encoding="utf-8") as f:
        minecraft = json.load(f)["minecraft"]
    return {
        "version": minecraft["version"],
        "manifest_sha1": minecraft["manifest_sha1"],
        "server_sha1": minecraft["server_sha1"],
        "client_sha1": minecraft["client_sha1"],
        "java_major": minecraft.get("java_major"),
    }


def resources_dir() -> Path:
    return ROOT / ".local" / "horizon-client" / pins()["version"]


def settings_path() -> Path:
    return ROOT / ".local" / "launcher-settings.json"


def sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runnable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def minecraft_candidates() -> list[Path]:
    """Where the official launcher, and a Prism/MultiMC root, usually keep their files."""
    home = Path.home()
    if sys.platform == "darwin":
        app = home / "Library" / "Application Support"
        return [app / "minecraft", app / "PrismLauncher", app / "multimc"]
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return [appdata / ".minecraft", appdata / "PrismLauncher", appdata / "MultiMC"]
    return [
        home / ".minecraft",
        home / ".var" / "app" / "com.mojang.Minecraft" / ".minecraft",
        home / ".local" / "share" / "PrismLauncher",
        home / ".local" / "share" / "multimc",
    ]


def classify_minecraft(folder: Path) -> str:
    """"minecraft" for a normal game folder, "prism" for a Prism/MultiMC root or instance."""
    if (folder / "mmc-pack.json").is_file() or (folder / "instances").is_dir():
        return "prism"
    if (folder / "minecraft" / "versions").is_dir():  # a Prism instance
        return "prism"
    return "minecraft"


def has_version(folder: Path, version: str) -> bool:
    if (folder / "versions" / version).is_dir():
        return True
    return (folder / "minecraft" / "versions" / version).is_dir()  # a Prism instance


def detect_minecraft() -> tuple[str, Path] | None:
    """The first folder on this machine that holds the pinned version."""
    version = pins()["version"]
    override = os.environ.get("HORIZON_MINECRAFT_DIR")
    candidates = ([Path(override)] if override else []) + minecraft_candidates()
    for folder in candidates:
        if folder.is_dir() and has_version(folder, version):
            return classify_minecraft(folder), folder
    return None


def server_jar_candidates() -> list[Path]:
    home = Path.home()
    version = pins()["version"]
    return [
        ROOT / ".local" / "minecraft" / version / "jars" / "server.jar",
        ROOT / ".local" / "downloads" / f"server-{version}.jar",
        home / "Downloads" / "server.jar",
        home / "Games" / "server.jar",
        home / "Desktop" / "server.jar",
    ]


def detected_server_jar() -> Path | None:
    want = pins()["server_sha1"]
    for path in server_jar_candidates():
        if path.is_file() and sha1(path) == want:
            return path
    return None


def resources_state() -> tuple[bool, bool]:
    """(prepared, sounds) for the folder the game is given, without running the checker."""
    folder = resources_dir()
    prepared = (folder / RESOURCES_MARK).is_file()
    return prepared, (folder / SOUNDS_MARK).is_file()


def check_resources() -> tuple[bool, list[str]]:
    """`horizon-prepare --check`: complete and current, or the gaps (12 ms, runs no Java)."""
    if not runnable(PREPARE_BIN):
        return False, ["the preparer is not built yet"]
    try:
        done = subprocess.run(
            [str(PREPARE_BIN), "--check", "--root", str(ROOT), "--output", str(resources_dir())],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as error:
        return False, [f"could not run the checker: {error}"]
    gaps = [line for line in done.stdout.splitlines() if line.strip()]
    return done.returncode == 0 and not gaps, gaps


# --------------------------------------------------------------------------- settings


def load_settings() -> dict:
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(values: dict) -> None:
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".json.part")
        partial.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
        partial.replace(path)
    except OSError:
        pass  # A launcher that cannot keep its settings still plays.


# --------------------------------------------------------------------------- downloads


def server_download(version: str, manifest_url: str = VERSION_MANIFEST) -> tuple[str, str, int]:
    """(url, sha1, size) of the pinned version's server jar, from Mojang's metadata."""
    cached = ROOT / ".local" / "minecraft" / version / "manifest.json"
    if cached.is_file():
        with open(cached, encoding="utf-8") as f:
            server = json.load(f)["downloads"]["server"]
        return server["url"], server["sha1"], int(server.get("size", 0))

    with urllib.request.urlopen(manifest_url, timeout=30) as reply:
        manifest = json.load(reply)
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        raise RuntimeError(f"Mojang's version list has no {version}")
    with urllib.request.urlopen(entry["url"], timeout=30) as reply:
        details = json.load(reply)
    server = details["downloads"]["server"]
    return server["url"], server["sha1"], int(server.get("size", 0))


def download_server_jar(log) -> Path:
    version = pins()["version"]
    url, want, size = server_download(version)
    if want != pins()["server_sha1"]:
        raise RuntimeError(
            f"Mojang's {version} server jar is {want}, "
            f"but this checkout pins {pins()['server_sha1']}"
        )
    target = ROOT / ".local" / "downloads" / f"server-{version}.jar"
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".jar.part")
    log(f"Downloading {url}")
    if size:
        log(f"  {size / 1e6:.0f} MB, checked against SHA-1 {want}")
    digest = hashlib.sha1()
    done = 0
    try:
        with urllib.request.urlopen(url, timeout=60) as reply, open(partial, "wb") as out:
            while True:
                chunk = reply.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if size and done % (16 << 20) < len(chunk):
                    log(f"  {done / 1e6:.0f} of {size / 1e6:.0f} MB")
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    if digest.hexdigest() != want:
        partial.unlink(missing_ok=True)
        raise RuntimeError("the downloaded server jar does not match the pinned SHA-1")
    partial.replace(target)
    log(f"Server jar ready: {target}")
    return target


def needs_version_json(lines) -> bool:
    """Whether a failed preparation is the one a rewritten version file causes."""
    return any("version file Horizon knows" in line for line in lines)


def fetch_version_json(log, base: str = "https://piston-meta.mojang.com") -> Path:
    """Mojang's own version file, for a launcher that rewrote the one in the game folder."""
    pin = pins()
    version = pin["version"]
    url = f"{base.rstrip('/')}/v1/packages/{pin['manifest_sha1']}/{version}.json"
    target = ROOT / ".local" / "minecraft" / version / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=30) as reply:
        data = reply.read()
    if hashlib.sha1(data).hexdigest() != pin["manifest_sha1"]:
        raise RuntimeError("the downloaded version file does not match the pinned SHA-1")
    target.write_bytes(data)
    log(f"Version file ready: {target}")
    return target


# --------------------------------------------------------------------------- commands


def prepare_command(minecraft: tuple[str, str] | None, jar: Path | None, sounds: bool) -> list[str]:
    command = [
        str(PREPARE_BIN),
        "--prepare",
        "--progress",
        "json",
        "--root",
        str(ROOT),
        "--output",
        str(resources_dir()),
    ]
    if minecraft:
        kind, path = minecraft
        command += ["--prism-dir" if kind == "prism" else "--minecraft-dir", path]
    if jar:
        command += ["--server-jar", str(jar)]
    if not sounds:
        command += ["--no-sounds"]
    return command


def game_command(game_dir: Path, extra: list[str] | None = None) -> list[str]:
    command = [
        str(GAME_BIN),
        "--resources",
        str(resources_dir()),
        "--game-dir",
        str(game_dir),
        "--home",
        str(game_dir),
    ]
    return command + list(extra or [])


def total_memory_gb() -> float | None:
    """Physical memory, or None when it cannot be read."""
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=5)
            return int(out.strip()) / 1e9
        if os.name != "nt":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024 / 1e9
    except Exception:
        return None
    return None


def build_jobs(low_memory: bool = False) -> int:
    """Cargo's parallel jobs: more speed, but each rustc can take a gigabyte or two."""
    if low_memory:
        return 1
    value = os.environ.get("HORIZON_BUILD_JOBS", "").strip()
    if value:
        try:
            return max(1, int(value))
        except ValueError:
            pass
    cores = os.cpu_count() or 4
    memory = total_memory_gb()
    # A first build on a small machine is what gets killed for memory; keep it modest there.
    cap = 4 if memory is not None and memory < 12 else 8
    return max(1, min(cores, cap))


def swap_gb() -> float | None:
    """Total swap the kernel reports, or None where it cannot be read."""
    try:
        if os.name != "nt" and sys.platform != "darwin":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("SwapTotal:"):
                        return int(line.split()[1]) * 1024 / 1e9
    except Exception:
        return None
    return None


def low_memory_environment() -> dict[str, str]:
    """Compiler settings that trade speed for peak memory, for a 4–8 GB machine."""
    existing = os.environ.get("RUSTFLAGS", "").strip()
    threads = "-Zthreads=1"
    # Keep any flags the caller set for other reasons, but never the repo's eight front-end threads.
    kept = " ".join(
        token for token in existing.split() if not token.startswith("-Zthreads")
    )
    return {
        "HORIZON_BUILD_JOBS": "1",
        "RUSTFLAGS": f"{threads} {kept}".strip(),
        # opt-level 1 is the big one: LLVM's optimiser is what grows with opt-level 3.
        "CARGO_PROFILE_FAST_OPT_LEVEL": "1",
        # No incremental cache competing for memory during a one-off first build.
        "CARGO_PROFILE_FAST_INCREMENTAL": "false",
    }


def low_memory_notes() -> str:
    """What a low-memory build assumes, including the swap a 4 GB machine needs."""
    memory = total_memory_gb()
    parts = []
    if memory is not None:
        parts.append(f"{memory:.1f} GB RAM detected")
    swap = swap_gb()
    if sys.platform == "linux":
        if swap is None or swap < 4:
            parts.append(
                "a build this size wants 16 GB of swap on a 4 GB machine; no swap was found"
                if not swap
                else f"only {swap:.1f} GB of swap; 16 GB is safer"
            )
        else:
            parts.append(f"{swap:.1f} GB swap")
    return "; ".join(parts)


def build_command(low_memory: bool = False) -> list[str]:
    cargo = os.environ.get("CARGO") or str(Path.home() / ".cargo" / "bin" / "cargo")
    if not Path(cargo).is_file():
        cargo = "cargo"
    return [
        cargo,
        "build",
        "--profile",
        "fast",
        "--jobs",
        str(build_jobs(low_memory)),
        "-p",
        "horizon-game",
        "-p",
        "horizon-prepare",
    ]


def logs_dir() -> Path:
    return ROOT / ".local" / "logs"


def split_extra_arguments(text: str) -> list[str]:
    if not text.strip():
        return []
    try:
        return shlex.split(text, posix=os.name != "nt")
    except ValueError:
        return text.split()


# --------------------------------------------------------------------------- self-test


def prebuilt_asset() -> str | None:
    """The release asset for this machine, or None where the fork publishes none."""
    machine = platform.machine().lower()
    if sys.platform.startswith("linux") and machine in ("x86_64", "amd64"):
        return PREBUILT_ASSET
    return None


def checksum_for(sums: str, name: str) -> str:
    """The SHA-256 a `sha256sum` file gives `name`; a missing or malformed line is an error."""
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            value = parts[0].lower()
            if re.fullmatch(r"[0-9a-f]{64}", value):
                return value
            break
    raise ValueError(f"{name} is not in {SHA256SUMS_ASSET}")


def fetch_json(url: str, timeout: int = 60):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"{url} answered {error.code} {error.reason}. GitHub limits anonymous lookups; "
            "wait a minute, or download the archive from the release page by hand."
        ) from error


def install_prebuilt(archive: Path, root: Path = ROOT) -> list[Path]:
    """Copy a release archive's programs into root/target/fast, where the launcher looks.

    Only the named binaries are taken; an archive with a path outside it, or without the game
    and the preparer, is refused.
    """
    dest = root / "target" / "fast"
    dest.mkdir(parents=True, exist_ok=True)
    partials: dict[str, Path] = {}
    try:
        with tarfile.open(archive, "r:*") as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if member.name.startswith("/") or ".." in parts:
                    raise ValueError(f"{archive.name} holds an unsafe path: {member.name}")
                if not member.isfile() or parts[-3:-1] != ("target", "fast"):
                    continue
                name = parts[-1]
                if name not in PREBUILT_BINARIES:
                    continue
                source = tar.extractfile(member)
                if source is None:
                    continue
                partial = dest / f"{name}.part"
                with open(partial, "wb") as out:
                    shutil.copyfileobj(source, out)
                os.chmod(partial, 0o755)
                partials[name] = partial
        missing = [name for name in ("horizon-client", "horizon-prepare") if name not in partials]
        if missing:
            raise ValueError(f"{archive.name} has no {', '.join(missing)}")
    except BaseException:
        for partial in partials.values():
            partial.unlink(missing_ok=True)
        raise
    # All present: only now do the installed programs change, so a bad archive leaves the
    # previous ones in place.
    installed = []
    for name, partial in partials.items():
        os.replace(partial, dest / name)
        installed.append(dest / name)
    return installed


def download_prebuilt(log=print, repo: str = RELEASE_REPO) -> int:
    """Fetch the latest release's archive, check its SHA-256 and install the programs."""
    asset = prebuilt_asset()
    if asset is None:
        log(
            "No prebuilt build is published for this machine: the fork ships Linux x86_64 "
            "programs. Build from source here instead (Play does it)."
        )
        return 1
    log(f"Finding {asset} in the latest release of {repo}…")
    release = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    assets = {item.get("name"): item for item in release.get("assets", [])}
    for name in (asset, SHA256SUMS_ASSET):
        if name not in assets:
            raise RuntimeError(
                f"The latest release of {repo} has no {name}; it holds: "
                + (", ".join(sorted(assets)) or "no assets")
            )
    sums_request = urllib.request.Request(
        assets[SHA256SUMS_ASSET]["browser_download_url"], headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(sums_request, timeout=60) as response:
        sums = response.read().decode("utf-8", "replace")
    want = checksum_for(sums, asset)

    with tempfile.TemporaryDirectory(prefix="horizon-prebuilt-") as scratch:
        archive = Path(scratch) / asset
        size = int(assets[asset].get("size") or 0)
        log(f"Downloading {asset}" + (f" ({size / 1e6:.0f} MB)" if size else "") + "…")
        request = urllib.request.Request(
            assets[asset]["browser_download_url"], headers={"User-Agent": USER_AGENT}
        )
        digest = hashlib.sha256()
        with urllib.request.urlopen(request, timeout=300) as response, open(archive, "wb") as out:
            total = int(response.headers.get("Content-Length") or size)
            done = 0
            tenth = -1
            while chunk := response.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total and done * 10 // total > tenth:
                    tenth = done * 10 // total
                    log(f"  {min(tenth, 10) * 10}%")
        got = digest.hexdigest()
        if got != want:
            raise RuntimeError(
                f"{asset} does not match {SHA256SUMS_ASSET}: expected {want}, got {got}. "
                "Nothing was installed."
            )
        installed = install_prebuilt(archive)
    log("Installed " + ", ".join(path.name for path in installed) + f" in {installed[0].parent}")
    log("Press Play; the first Play prepares the game files from your Minecraft copy.")
    return 0


def self_test(as_json: bool = False) -> int:
    """Report what the launcher would use, without opening a window."""
    version = pins()["version"]
    detected = detect_minecraft()
    jar = detected_server_jar()
    prepared, sounds = resources_state()
    complete, gaps = check_resources()
    setup = {
        "version": version,
        "root": str(ROOT),
        "resources": str(resources_dir()),
        "prepared": prepared,
        "complete": complete,
        "gaps": gaps,
        "sounds": sounds,
        "game_binary": str(GAME_BIN),
        "game_built": runnable(GAME_BIN),
        "prepare_binary": str(PREPARE_BIN),
        "prepare_built": runnable(PREPARE_BIN),
        "minecraft": None if not detected else {"kind": detected[0], "path": str(detected[1])},
        "server_jar": None if not jar else {"path": str(jar), "sha1": sha1(jar)},
        "game_dir": str(settings_game_dir()),
        "memory_gb": total_memory_gb(),
        "swap_gb": swap_gb(),
        "tk": tk is not None,
        "tk_version": None if tk is None else str(tk.TkVersion),
    }
    if as_json:
        print(json.dumps(setup, indent=2))
    else:
        print(f"python           {sys.executable} ({sys.version.split()[0]})")
        if setup["tk"]:
            print(f"tkinter          yes ({setup['tk_version']})")
        else:
            print("tkinter          NO — the window cannot open; run tools/launcher.sh")
        if setup["memory_gb"] is not None:
            memory = f"{setup['memory_gb']:.1f} GB"
            if setup["swap_gb"]:
                memory += f", {setup['swap_gb']:.1f} GB swap"
            print(f"memory           {memory}")
        print(f"checkout         {setup['root']}")
        print(
            f"minecraft {version}   "
            + (setup["minecraft"]["path"] if setup["minecraft"] else "not found (pick it in the window)")
        )
        print(
            "server jar       "
            + (setup["server_jar"]["path"] if setup["server_jar"] else "not here (the launcher downloads it)")
        )
        print(
            f"resources        {'ready' if setup['complete'] else 'not ready'}"
            + (", sounds" if setup["sounds"] else ", NO sounds")
        )
        for gap in setup["gaps"]:
            print(f"                 {gap}")
        print(f"game binary      {'built' if setup['game_built'] else 'not built yet'}")
        print(f"prepare binary   {'built' if setup['prepare_built'] else 'not built yet'}")
    return 0 if setup["complete"] and setup["game_built"] and setup["tk"] else 1


def settings_game_dir() -> Path:
    return Path(load_settings().get("game_dir") or DEFAULT_GAME_DIR).expanduser()


# --------------------------------------------------------------------------- window


class App:
    """The whole window. Every slow step runs on a thread and reports through `queue`."""

    def __init__(self, root, settings: dict | None = None, automatic: bool = False) -> None:
        self.root = root
        self.queue: queue.Queue = queue.Queue()
        self.settings = dict(settings or load_settings())
        self.automatic = automatic  # smoke tests: answer prompts with yes
        self.busy: str | None = None
        self.process: subprocess.Popen | None = None
        self.cancel_requested = False
        self.game: subprocess.Popen | None = None
        self.version = pins()["version"]
        self.last_lines: deque[str] = deque(maxlen=80)
        self.game_log: Path | None = None

        detected = detect_minecraft()
        minecraft = self.settings.get("minecraft") or (str(detected[1]) if detected else "")
        jar = self.settings.get("server_jar") or str(detected_server_jar() or "")
        game_dir = self.settings.get("game_dir") or str(DEFAULT_GAME_DIR)

        self.minecraft_var = tk.StringVar(value=minecraft)
        self.jar_var = tk.StringVar(value=jar)
        self.game_var = tk.StringVar(value=game_dir)
        self.sounds_var = tk.BooleanVar(value=bool(self.settings.get("sounds", True)))
        memory = total_memory_gb()
        low_memory_default = bool(self.settings.get("low_memory", memory is not None and memory < 8))
        self.low_memory_var = tk.BooleanVar(value=low_memory_default)
        self.extra_var = tk.StringVar(value=str(self.settings.get("extra_args", "")))
        self.status_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(value="")

        self.build_window()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self.write(
            "Press Play. The first run builds the game and prepares your files; later runs start "
            "in seconds."
        )
        self.root.after(80, self.drain)

    # -- building the window

    def build_window(self) -> None:
        # Modern Tk (8.6+) follows the system appearance, including dark mode, so leave "aqua"
        # in place there. Older Tk (8.5, the one macOS ships) is not dark-mode aware and renders
        # black-on-black, so fall back to "clam" with explicit light colours.
        try:
            style = ttk.Style(self.root)
            use_clam = tk.TkVersion < 8.6 or "aqua" not in style.theme_names()
            if use_clam and "clam" in style.theme_names():
                style.theme_use("clam")
                style.configure("TFrame", background="#f2f2f2")
                style.configure("TLabel", background="#f2f2f2", foreground="#1a1a1a")
                style.configure("TButton", background="#e0e0e0", foreground="#1a1a1a")
                style.configure("TCheckbutton", background="#f2f2f2", foreground="#1a1a1a")
                style.configure("TEntry", fieldbackground="#ffffff", foreground="#1a1a1a")
                style.configure("TProgressbar", background="#2a7de1")
                self.root.configure(background="#f2f2f2")
        except Exception:
            pass
        self.root.title(f"Horizon {self.version} — offline, no account")
        self.root.minsize(780, 600)
        self.root.geometry("800x620+120+120")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        frame = ttk.Frame(self.root, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(8, weight=1)

        title_font = tkfont.nametofont("TkDefaultFont").copy()
        title_font.configure(size=20, weight="bold")
        header = ttk.Frame(frame)
        header.grid(row=0, column=0, columnspan=4, sticky="we", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Horizon", font=title_font).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=f"Minecraft Java Edition {self.version}, in Rust — no account, no sign-in",
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(header, text="offline").grid(row=0, column=1, rowspan=2, sticky="e")

        self.field(frame, 1, "Minecraft folder", self.minecraft_var, self.pick_minecraft, "Find")
        self.field(frame, 2, "Server file", self.jar_var, self.pick_jar, "Download")
        self.field(frame, 3, "Worlds & settings", self.game_var, self.pick_game, None)
        self.field(frame, 4, "Extra game arguments (optional)", self.extra_var, None, None)

        options = ttk.Frame(frame)
        options.grid(row=5, column=0, columnspan=4, sticky="we", pady=(6, 2))
        ttk.Checkbutton(
            options,
            text="Copy the sounds (about 380 MB)",
            variable=self.sounds_var,
        ).pack(side="left")
        ttk.Checkbutton(
            options,
            text="Low-memory device (4–8 GB): one compiler job",
            variable=self.low_memory_var,
            command=self.refresh,
        ).pack(side="left", padx=(18, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=4, sticky="we", pady=(10, 4))
        self.play_button = ttk.Button(buttons, text="Play", command=self.play)
        self.play_button.pack(side="left")
        self.prepare_button = ttk.Button(buttons, text="Prepare game files", command=self.prepare)
        self.prepare_button.pack(side="left", padx=(8, 0))
        self.prebuilt_button = ttk.Button(
            buttons, text="Download prebuilt", command=self.install_prebuilt
        )
        self.prebuilt_button.pack(side="left", padx=(8, 0))
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.stop_button = ttk.Button(buttons, text="Stop game", command=self.stop_game, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Check again", command=self.refresh).pack(side="right")

        self.progress = ttk.Progressbar(frame, maximum=1.0)
        self.progress.grid(row=7, column=0, columnspan=4, sticky="we", pady=(4, 4))

        status = ttk.Frame(frame)
        status.grid(row=8, column=0, columnspan=4, sticky="new")
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.detail_var, foreground="#666").grid(
            row=1, column=0, sticky="w"
        )

        log_frame = ttk.Frame(frame)
        log_frame.grid(row=9, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        frame.rowconfigure(9, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(
            log_frame,
            height=13,
            wrap="word",
            state="disabled",
            background="#ffffff",
            foreground="#1a1a1a",
            insertbackground="#1a1a1a",
            font=tkfont.nametofont("TkFixedFont"),
            relief="solid",
            borderwidth=1,
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        self.log.tag_configure("error", foreground="#a40000")
        self.log.tag_configure("good", foreground="#006000")
        self.log.tag_configure("quiet", foreground="#666666")

        footer = ttk.Frame(frame)
        footer.grid(row=10, column=0, columnspan=4, sticky="we", pady=(8, 0))
        ttk.Button(footer, text="Open worlds folder", command=self.open_game_folder).pack(side="left")
        ttk.Button(footer, text="Open game log", command=self.open_game_log).pack(side="left", padx=8)
        ttk.Label(footer, text=f"resources: {resources_dir()}", foreground="#666").pack(side="right")

    def field(self, frame, row, label, variable, browse, extra) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="we", padx=(10, 8), pady=3)
        if browse:
            ttk.Button(frame, text="Browse…", command=browse).grid(row=row, column=2, pady=3)
        if extra:
            button = ttk.Button(
                frame,
                text=extra,
                command=self.download if extra == "Download" else self.find_minecraft,
            )
            button.grid(row=row, column=3, padx=(8, 0), pady=3)
            if extra == "Download":
                self.download_button = button

    # -- choosing files

    def pick_minecraft(self) -> None:
        chosen = filedialog.askdirectory(title="The folder your Minecraft launcher uses")
        if chosen:
            self.minecraft_var.set(chosen)
            self.refresh()

    def pick_jar(self) -> None:
        chosen = filedialog.askopenfilename(
            title=f"{self.version} server.jar",
            filetypes=[("Java archives", "*.jar"), ("All files", "*")],
        )
        if chosen:
            self.jar_var.set(chosen)
            self.refresh()

    def pick_game(self) -> None:
        chosen = filedialog.askdirectory(title="Where worlds and settings live")
        if chosen:
            self.game_var.set(chosen)
            self.refresh()

    def find_minecraft(self) -> None:
        found = detect_minecraft()
        if not found:
            self.warn(
                "Minecraft not found",
                f"No folder with Minecraft {self.version} was found.\n\n"
                "Use Browse… next to \"Minecraft folder\" and pick the folder your launcher "
                "installed the game into.",
            )
            return
        self.minecraft_var.set(str(found[1]))
        self.refresh()

    def open_game_folder(self) -> None:
        self.reveal(Path(self.game_var.get().strip() or DEFAULT_GAME_DIR))

    def open_game_log(self) -> None:
        self.reveal(self.game_log or (Path(self.game_var.get().strip() or DEFAULT_GAME_DIR) / "logs" / "latest.log"))

    def reveal(self, path: Path) -> None:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            elif os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as error:
            self.write(f"Could not open {path}: {error}", "error")

    # -- state and log

    def refresh(self) -> None:
        complete, gaps = check_resources()
        _, sounds = resources_state()
        built = runnable(GAME_BIN) and runnable(PREPARE_BIN)
        if not runnable(GAME_BIN):
            status = "The game is not built yet — Play builds it first."
            if prebuilt_asset() is not None:
                status = (
                    "The game is not built yet — Download prebuilt (no compiling), or Play to "
                    "build it."
                )
        elif not runnable(PREPARE_BIN):
            status = "The preparer is not built yet — Play builds it first."
        elif not complete:
            status = "The game files need preparing — Play does it."
        elif self.sounds_var.get() and not sounds:
            status = "Ready, but the sounds are missing — Play copies them."
        else:
            status = "Ready — press Play."
        self.status_var.set(status)
        detail = f"Minecraft {self.version}"
        if self.low_memory_var.get():
            detail += " · low-memory build"
        if gaps and built:
            detail += f" · {len(gaps)} thing(s) to prepare"
        if not self.minecraft_var.get().strip():
            detail += " · Minecraft folder not set"
        self.detail_var.set(detail)
        self.progress["value"] = 1.0 if complete and (sounds or not self.sounds_var.get()) else 0.0
        # Downloading only makes sense where there is an archive for this machine and the
        # programs are not already here.
        self.prebuilt_button.configure(
            state="normal" if prebuilt_asset() and not built else "disabled"
        )

    def write(self, text: str, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def warn(self, title: str, text: str) -> None:
        self.write(text, "error")
        if not self.automatic:
            messagebox.showwarning(title, text)

    def error(self, title: str, text: str) -> None:
        self.write(text, "error")
        if not self.automatic:
            messagebox.showerror(title, text)

    def confirm(self, title: str, text: str) -> bool:
        if self.automatic:
            self.write(text, "quiet")
            return True
        return messagebox.askyesno(title, text)

    # -- running a process or a job

    def set_busy(self, busy: str | None) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.play_button, self.prepare_button, self.download_button):
            button.configure(state=state)
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if not busy:
            running = self.game is not None and self.game.poll() is None
            self.stop_button.configure(state="normal" if running else "disabled")

    def run_process(
        self,
        command: list[str],
        done=None,
        label: str | None = None,
        logfile: Path | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> None:
        if self.busy:
            self.write("Another step is still running; wait for it to finish.", "quiet")
            return
        self.last_lines.clear()
        self.cancel_requested = False
        self.set_busy(label or "working")
        self.progress["value"] = 0.0
        self.write("$ " + " ".join(command), "quiet")
        if logfile is not None:
            try:
                logfile.parent.mkdir(parents=True, exist_ok=True)
                logfile.write_text("")
                self.write(f"Output is also saved to {logfile}", "quiet")
            except OSError:
                logfile = None

        def work() -> None:
            nonlocal logfile
            code = 127
            try:
                environment = dict(os.environ)
                environment["PATH"] = (
                    str(Path.home() / ".cargo" / "bin") + os.pathsep + environment.get("PATH", "")
                )
                if env_extra:
                    environment.update(env_extra)
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    env=environment,
                    start_new_session=True,
                )
                self.process = process
                if self.cancel_requested:
                    terminate(process)
                assert process.stdout is not None
                for line in process.stdout:
                    clean = ANSI.sub("", line.rstrip("\n"))
                    if logfile is not None:
                        try:
                            with open(logfile, "a", encoding="utf-8") as out:
                                out.write(clean + "\n")
                        except OSError:
                            logfile = None
                    self.queue.put(("line", clean))
                code = process.wait()
            except FileNotFoundError:
                self.queue.put(("line", f"{command[0]} was not found on this machine"))
            except Exception as error:
                self.queue.put(("line", f"could not run {command[0]}: {error}"))
            finally:
                self.process = None
            if self.cancel_requested and code == 0:
                code = 130
            self.queue.put(("done", code, done))

        threading.Thread(target=work, daemon=True).start()

    def run_job(self, job, done=None, label: str = "working") -> None:
        if self.busy:
            self.write("Another step is still running; wait for it to finish.", "quiet")
            return
        self.set_busy(label)
        self.cancel_button.configure(state="disabled")  # a download is short; let it finish
        self.progress["value"] = 0.0

        def log(line: str) -> None:
            self.queue.put(("line", str(line)))

        def work() -> None:
            code = 0
            try:
                job(log)
            except Exception as error:
                self.queue.put(("line", f"error: {error}"))
                code = 1
            self.queue.put(("done", code, done))

        threading.Thread(target=work, daemon=True).start()

    def cancel(self) -> None:
        if not self.busy:
            return
        self.cancel_requested = True
        self.write("Cancelling…", "quiet")
        if self.process is not None and self.process.poll() is None:
            terminate(self.process)

    def drain(self) -> None:
        while True:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                break
            if item[0] == "line":
                self.line(item[1])
            elif item[0] == "game":
                self.write(item[1], "quiet")
            elif item[0] == "game_exit":
                self.game = None
                self.stop_button.configure(state="disabled")
                self.write(item[1])
                self.refresh()
            elif item[0] == "done":
                self.finished(item[1], item[2])
        self.root.after(80, self.drain)

    def line(self, text: str) -> None:
        if text.strip():
            self.last_lines.append(text)
        if text.startswith("{"):
            try:
                event = json.loads(text)
            except ValueError:
                event = None
            if isinstance(event, dict):
                if "fraction" in event:
                    self.progress["value"] = float(event["fraction"])
                    if float(event["fraction"]) >= 0.9:
                        self.status_var.set("Copying the sounds — this is the big step…")
                    return
                if "message" in event:
                    self.write(str(event["message"]))
                    return
                if "error" in event:
                    self.write("error: " + str(event["error"]), "error")
                    return
        if text.strip():
            self.write(text, "error" if "error" in text.lower() else None)

    def finished(self, code: int, done) -> None:
        self.set_busy(None)
        if code == 0:
            self.progress["value"] = 1.0
        elif code in (130, -15):
            self.write("Cancelled.", "quiet")
        else:
            self.write(f"Stopped with exit code {code}.", "error")
        self.refresh()
        if done:
            done(code)

    # -- the steps

    def play(self) -> None:
        if self.busy:
            return
        if self.game is not None and self.game.poll() is None:
            self.write("The game is already running.")
            return
        if not runnable(GAME_BIN) or not runnable(PREPARE_BIN):
            low = bool(self.low_memory_var.get())
            memory = total_memory_gb()
            if low:
                extra = (
                    "\n\nThis machine has "
                    + (f"{memory:.0f} GB RAM. " if memory is not None else "")
                    + "The low-memory build uses one compiler job and one thread, so it can take "
                    "a few hours on 4 GB. Keep the window open and close other apps."
                )
            else:
                extra = ""
            if not self.confirm(
                "Build the game",
                "Horizon is not built yet. Build it now?\n\n"
                "Compiling the game takes a few minutes the first time; the window stays open and "
                "shows the build's progress. It happens once." + extra,
            ):
                return
            self.build(then=lambda code: code == 0 and self.play())
            return
        mode = self.preflight()
        if mode == "stop":
            return
        if mode == "download":
            self.download(then=lambda code: code == 0 and self.play())
            return
        complete, _ = check_resources()
        _, sounds = resources_state()
        if not complete or (self.sounds_var.get() and not sounds):
            self.prepare(then=lambda code: code == 0 and self.start_game())
            return
        self.start_game()

    def prepare(self, then=None, retry: bool = True) -> None:
        mode = self.preflight()
        if mode == "stop":
            return
        if mode == "download":
            self.download(then=lambda code: code == 0 and self.prepare(then, retry))
            return
        folder = self.minecraft_var.get().strip()
        jar = Path(self.jar_var.get().strip()) if self.jar_var.get().strip() else None
        minecraft = (classify_minecraft(Path(folder)), folder)
        sounds = self.sounds_var.get()

        def done(code: int) -> None:
            if code != 0 and retry and needs_version_json(self.last_lines):
                self.write(
                    "Your launcher rewrote Minecraft's version file. Fetching Mojang's own copy, "
                    "then preparing again…",
                    "quiet",
                )
                self.run_job(
                    lambda log: fetch_version_json(log),
                    lambda fetched: fetched == 0 and self.prepare(then, retry=False),
                    "fixing the version file",
                )
                return
            if code != 0 and any("Java" in line for line in self.last_lines):
                self.write(
                    "The preparation needs a Java 25 runtime to read your Minecraft files. "
                    "Install one (macOS: brew install openjdk@25) and press Play again.",
                    "error",
                )
            if then:
                then(code)

        low_memory = bool(self.low_memory_var.get())
        if low_memory:
            self.write(
                "Low-memory preparation: one worker thread and a 1 GB Java heap per step, so the "
                "exporters cannot grow past what this machine has. Copying the sounds still "
                "takes a while; the window stays open.",
                "quiet",
            )
        self.run_process(
            prepare_command(minecraft, jar, sounds),
            done,
            "preparing",
            env_extra=(
                {"HORIZON_PREPARE_JOBS": "1", "HORIZON_PREPARE_HEAP": "1G"}
                if low_memory
                else None
            ),
        )

    def build(self, then=None) -> None:
        low_memory = bool(self.low_memory_var.get())
        stamp = time.strftime("%Y%m%d-%H%M%S")
        logfile = logs_dir() / f"build-{stamp}.log"
        if low_memory:
            self.write(
                "Low-memory build: one compiler job, one front-end thread, opt-level 1. "
                + low_memory_notes()
                + ". The game itself runs a little slower than a normal build; that is the "
                "trade for finishing on this machine.",
                "quiet",
            )
            if sys.platform == "linux" and (swap_gb() or 0) < 4:
                self.write(
                    "A first build on 4 GB needs disk swap. If it is missing, run once in a "
                    "terminal:\n"
                    "    sudo fallocate -l 16G /swapfile && sudo chmod 600 /swapfile && "
                    "sudo mkswap /swapfile && sudo swapon /swapfile\n"
                    "The build will take a while; keep the window open.",
                    "quiet",
                )

        def done(code: int) -> None:
            killed = code < 0 or code == 137 or any(
                marker in line.lower()
                for line in self.last_lines
                for marker in ("signal: 9", "sigkill", "killed")
            )
            if killed and low_memory:
                self.write(
                    "The low-memory build was still killed. It is already using one job and one "
                    "thread, so the machine has no room left: close every other app, add the "
                    "16 GB swap file above if you have not, and run it again.\n"
                    f"The full build log is {logfile}. A machine with 8 GB or more builds this "
                    "in a fraction of the time.",
                    "error",
                )
            elif killed:
                self.write(
                    "The build was killed. On a first build that is usually the system running "
                    "out of memory: close other apps, then try again with fewer parallel jobs:\n"
                    f"    HORIZON_BUILD_JOBS=4 ./tools/launcher.sh\n"
                    f"or tick \"Low-memory device\" in the launcher.\n"
                    f"The full build log is {logfile}",
                    "error",
                )
            elif code != 0:
                self.write(f"The build failed. The full build log is {logfile}", "error")
            if then:
                then(code)

        self.run_process(
            build_command(low_memory),
            done,
            "building",
            logfile,
            low_memory_environment() if low_memory else None,
        )

    def download(self, then=None) -> None:
        result: dict[str, Path] = {}

        def job(log) -> None:
            result["path"] = download_server_jar(log)

        def done(code: int) -> None:
            if code == 0 and "path" in result:
                self.jar_var.set(str(result["path"]))
                self.refresh()
            if then:
                then(code)

        self.run_job(job, done, "downloading the server jar")

    def install_prebuilt(self) -> None:
        """Install the fork's prebuilt programs, for a machine that cannot build them."""
        asset = prebuilt_asset()
        if asset is None:
            self.warn(
                "Download prebuilt",
                "No prebuilt build is published for this machine. The fork ships Linux x86_64 "
                "programs; on other systems Play builds the game from source.",
            )
            return
        if not self.confirm(
            "Download Horizon",
            "Download the prebuilt Linux build (about 75 MB) and install the game's programs "
            "in this folder?\n\nNothing is compiled. The archive is checked against the "
            "release's SHA-256 before it is used, and Play prepares the game files afterwards.",
        ):
            return

        def done(code: int) -> None:
            self.refresh()
            if code == 0:
                self.write("Prebuilt build installed — press Play.", "good")

        self.run_job(lambda log: download_prebuilt(log), done, "downloading Horizon")

    def preflight(self) -> str:
        """Check the fields Play and Prepare need: "ok", "download" or "stop"."""
        folder_text = self.minecraft_var.get().strip()
        if not folder_text:
            found = detect_minecraft()
            if found:
                folder_text = str(found[1])
                self.minecraft_var.set(folder_text)
            else:
                self.warn(
                    "Minecraft folder",
                    f"Horizon could not find Minecraft {self.version}.\n\n"
                    "Use Browse… next to \"Minecraft folder\" and pick the folder your launcher "
                    "installed it into.",
                )
                return "stop"
        folder = Path(folder_text).expanduser()
        if not folder.is_dir():
            self.error("Minecraft folder", f"{folder} does not exist. Pick it again with Browse….")
            return "stop"
        if not has_version(folder, self.version):
            self.warn(
                "Minecraft version",
                f"{folder} does not hold Minecraft {self.version}.\n\n"
                "Pick the folder your launcher installed 26.3 into, or prepare that version "
                "in the launcher first.",
            )
            return "stop"

        jar_text = self.jar_var.get().strip()
        jar = Path(jar_text).expanduser() if jar_text else None
        if jar is not None and not jar.is_file():
            self.error("Server file", f"{jar} does not exist. Pick it again with Browse….")
            return "stop"
        if jar is None:
            found = detected_server_jar()
            if found:
                jar = found
                self.jar_var.set(str(found))
        if jar is not None and sha1(jar) != pins()["server_sha1"]:
            self.error(
                "Server file",
                f"{jar} is not the {self.version} server jar this build expects.\n\n"
                f"Expected SHA-1 {pins()['server_sha1']}.\n"
                "Press Download to let the launcher fetch Mojang's copy, or pick another file.",
            )
            return "stop"
        if jar is None:
            if not self.confirm(
                "Minecraft server file",
                f"Horizon needs the Minecraft {self.version} server jar (about 60 MB) to read your "
                "game files, and it is not on this machine.\n\n"
                "Download it from Mojang now? It is checked against the SHA-1 this build pins and "
                "is only read; the game itself never runs Java.",
            ):
                self.write(
                    "Press Download next to \"Server file\" when you are ready, or pick your own copy.",
                    "quiet",
                )
                return "stop"
            return "download"
        return "ok"

    def start_game(self) -> None:
        game_dir = Path(self.game_var.get().strip() or DEFAULT_GAME_DIR).expanduser()
        try:
            (game_dir / "logs").mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.error("Worlds & settings", f"Cannot create {game_dir}: {error}")
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.game_log = game_dir / "logs" / f"launcher-{stamp}.log"
        command = game_command(game_dir, split_extra_arguments(self.extra_var.get()))
        self.write("$ " + " ".join(command), "quiet")
        try:
            with open(self.game_log, "wb") as out:
                self.game = subprocess.Popen(
                    command,
                    cwd=str(game_dir),
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except Exception as error:
            self.error("Start the game", f"Could not start {command[0]}: {error}")
            return
        self.stop_button.configure(state="normal")
        self.status_var.set(f"Playing — Minecraft {self.version}, no account")
        self.write(f"The game is starting (pid {self.game.pid}). Its output is in {self.game_log}", "good")
        threading.Thread(target=self.follow, args=(self.game_log, self.game), daemon=True).start()

    def follow(self, path: Path, process: subprocess.Popen) -> None:
        position = 0
        while process.poll() is None:
            try:
                with open(path, "rb") as f:
                    f.seek(position)
                    chunk = f.read()
                    position += len(chunk)
            except OSError:
                chunk = b""
            for line in chunk.decode("utf-8", "replace").splitlines():
                self.queue.put(("game", ANSI.sub("", line)))
            time.sleep(0.5)
        code = process.poll()
        self.queue.put(("game_exit", f"The game exited (code {code})."))

    def stop_game(self) -> None:
        if self.game is not None and self.game.poll() is None:
            self.write("Asking the game to stop…", "quiet")
            terminate(self.game)

    def save(self) -> None:
        save_settings(
            {
                "minecraft": self.minecraft_var.get().strip(),
                "server_jar": self.jar_var.get().strip(),
                "game_dir": self.game_var.get().strip(),
                "sounds": bool(self.sounds_var.get()),
                "low_memory": bool(self.low_memory_var.get()),
                "extra_args": self.extra_var.get().strip(),
            }
        )

    def close(self) -> None:
        if self.busy and not self.confirm("Quit", "A step is still running. Cancel it and quit?"):
            return
        self.cancel()
        self.save()
        if self.game is not None and self.game.poll() is None:
            self.write("The game keeps running after this window closes.", "quiet")
        self.root.destroy()


def terminate(process: subprocess.Popen) -> None:
    """Stop a process and the children it started (the preparer runs Java exporters)."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
            )
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except Exception:
        try:
            process.terminate()
        except Exception:
            return
    if os.name != "nt":
        def finish() -> None:
            time.sleep(5)
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    pass

        threading.Thread(target=finish, daemon=True).start()


# --------------------------------------------------------------------------- entry point


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Horizon's offline launcher")
    parser.add_argument("--self-test", action="store_true", help="check the setup and exit")
    parser.add_argument(
        "--low-memory",
        action="store_true",
        help="for a 4-8 GB machine: one compiler job, a 1 GB Java heap while preparing",
    )
    parser.add_argument("--json", action="store_true", help="with --self-test: print JSON")
    parser.add_argument(
        "--download-prebuilt",
        action="store_true",
        help="download and install the prebuilt Linux build, then exit",
    )
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-prepare", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-play", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-build", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test(args.json)
    if args.download_prebuilt:
        return download_prebuilt(print)

    if tk is None:
        print(
            "launcher: this Python has no tkinter, so the window cannot open.\n"
            "Run tools/launcher.sh (it finds a Python that has Tk), or install Tk:\n"
            "   macOS (Homebrew): brew install python-tk\n"
            "   Debian/Ubuntu:    sudo apt install python3-tk\n"
            "Without a window: ./tools/play-offline.sh still plays.",
            file=sys.stderr,
        )
        return 1

    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.15)
    except Exception:
        pass
    app = App(
        root,
        automatic=args.smoke_test or args.smoke_prepare or args.smoke_play or args.smoke_build,
    )
    if args.low_memory:
        app.low_memory_var.set(True)
        app.refresh()

    if args.smoke_prepare:
        state = {"started": False}

        def prepare_tick() -> None:
            if not state["started"]:
                if not app.busy:
                    state["started"] = True
                    app.prepare()
            elif not app.busy:
                print(f"prepare finished; status: {app.status_var.get()}")
                app.save()
                root.destroy()
                return
            root.after(200, prepare_tick)

        root.after(400, prepare_tick)
    elif args.smoke_build:
        state = {"started": False}

        def build_tick() -> None:
            if not state["started"]:
                if not app.busy:
                    state["started"] = True
                    app.build()
            elif not app.busy:
                logs = sorted(logs_dir().glob("build-*.log"))
                where = logs[-1] if logs else "none"
                print(f"build finished; status: {app.status_var.get()}; log: {where}")
                root.destroy()
                return
            root.after(300, build_tick)

        root.after(400, build_tick)
    elif args.smoke_play:
        import tempfile

        scratch = tempfile.mkdtemp(prefix="horizon-launcher-smoke-")
        socket = Path(scratch) / "ctl.sock"
        ctl = ROOT / "target" / "fast" / "horizon-ctl"
        app.game_var.set(scratch)
        state = {"started": False, "waited": 0, "reached": False}

        def play_tick() -> None:
            state["waited"] += 1
            if not state["started"]:
                if not app.busy:
                    state["started"] = True
                    app.extra_var.set(
                        f"--offscreen --control --control-socket {socket} "
                        "--world SmokePlay --seed 7"
                    )
                    app.play()
            elif app.game is not None and app.game.poll() is None:
                if state["waited"] % 4 == 0 and ctl.is_file():
                    try:
                        answer = subprocess.run(
                            [str(ctl), "--socket", str(socket), "state"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        screen = json.loads(answer.stdout).get("screen")
                        state["reached"] = screen == "playing"
                    except Exception:
                        pass
                if state["reached"] or state["waited"] > 90:
                    print(
                        f"game started; pid {app.game.pid}; "
                        f"{'screen: playing' if state['reached'] else 'no world in 45 s'}; "
                        f"status: {app.status_var.get()}"
                    )
                    if ctl.is_file():
                        subprocess.run(
                            [str(ctl), "--socket", str(socket), "quit"],
                            capture_output=True,
                            timeout=10,
                        )
                    app.stop_game()
                    root.after(
                        1500, lambda: (shutil.rmtree(scratch, ignore_errors=True), root.destroy())
                    )
                    return
            elif not app.busy and app.game is None and state["waited"] > 40:
                print(f"game did not start; status: {app.status_var.get()}")
                root.destroy()
                return
            root.after(500, play_tick)

        root.after(400, play_tick)
    elif args.smoke_test:

        def report() -> None:
            root.update_idletasks()
            print(
                f"window {root.winfo_width()}x{root.winfo_height()}, "
                f"{len(root.winfo_children()[0].winfo_children())} widgets, "
                f"status: {app.status_var.get()}"
            )
            root.destroy()

        root.after(1200, report)

    try:
        root.lift()
        root.focus_force()
        root.attributes("-topmost", True)
        root.after(1500, lambda: root.attributes("-topmost", False))
    except Exception:
        pass
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
