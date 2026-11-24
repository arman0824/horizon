# Horizon 26.3 — offline build for Linux, Windows and macOS

Minecraft: Java Edition 26.3 rewritten in Rust. **No account, no sign-in, no compiler.** Each
archive holds the finished programs, so nothing has to be built on your machine.

| Your machine | Download | Open it with |
| --- | --- | --- |
| Linux x86_64 (glibc 2.35 and newer) | `horizon-linux-x86_64.tar.gz` | `./tools/launcher.sh` |
| Windows x86_64 | `horizon-windows-x86_64.zip` | `Start Horizon.bat` |
| Apple Silicon Mac (M1 and later) | `horizon-macos-arm64.tar.gz` | `Horizon Launcher.command` |

`SHA256SUMS` covers all three archives.

## What is in the archive

```
horizon-linux-x86_64/            horizon-macos-arm64/          horizon-windows-x86_64/
  target/fast/horizon-client       (same layout)                target/fast/horizon-client.exe
  target/fast/horizon-prepare                                    target/fast/horizon-prepare.exe
  target/fast/horizon-ctl                                        target/fast/horizon-ctl.exe
  tools/launcher.sh                tools/launcher.sh             Start Horizon.bat
  tools/launcher.py                tools/launcher.py             tools/launcher.py
  tools/play-offline.sh            tools/play-offline.sh
                                   Horizon Launcher.command
  mods/horizon/src/test/java/      the exporter sources, compiled once on first prepare
  research-lock.json               the Minecraft 26.3 files it checks
  README.md, LICENSE, LICENSES/, docs/release-notes-offline.md
```

The archives do **not** contain Minecraft's jars, assets or sounds, and they cannot: those are
Mojang's files. The launcher reads the copy you already own and prepares the game's resources from
it. The game itself never runs Java; Java is used once, during preparation.

## What you need

- **Minecraft 26.3 installed once** by any launcher (official, Prism, MultiMC, SKLauncher,
  TLauncher…), or that `.minecraft` folder copied over. You must own the game.
- **Java 25 with `javac`** for the preparation step. The first prepare compiles Horizon's exporter
  classes from the sources in the archive — about 20 seconds, once.
  - Linux: `sudo apt install openjdk-25-jdk` (or your distribution's equivalent)
  - macOS: `brew install openjdk@25`
  - Windows: [Temurin 25](https://adoptium.net/?specification=25) or any JDK 25
  - Check with `java -version` and `javac -version`.
- **Python 3 with tkinter** for the window.
  - Linux: `sudo apt install python3-tk` (most systems have it)
  - macOS: the system Python has Tk; with Homebrew, `brew install python-tk`
  - Windows: install from [python.org](https://www.python.org/downloads/) and leave
    "tcl/tk and IDLE" ticked. The Microsoft Store build has no Tcl/Tk.
- **Graphics and sound** as for any game: a Vulkan driver on Linux, the usual Direct3D/Metal
  support on Windows and macOS.

## Install and play

Linux:

```sh
sha256sum -c SHA256SUMS --ignore-missing
tar xzf horizon-linux-x86_64.tar.gz
cd horizon-linux-x86_64
./tools/launcher.sh
```

macOS (Terminal, or double-click `Horizon Launcher.command` in Finder):

```sh
shasum -a 256 -c SHA256SUMS --ignore-missing
tar xzf horizon-macos-arm64.tar.gz
cd horizon-macos-arm64
./tools/launcher.sh
```

Windows (PowerShell, after **Extract All** on the zip):

```powershell
cd horizon-windows-x86_64
.\"Start Horizon.bat"
```

In the window: check **Minecraft folder** (found automatically; **Browse…** if not), leave
**Copy the sounds** on, press **Play**. The first Play prepares the game files from your Minecraft
copy — a few minutes — and opens the game. Later Plays start immediately.

Without a window: `./tools/play-offline.sh` on Linux and macOS after preparing once with
`./target/fast/horizon-prepare --prepare --server-jar /path/to/server.jar`.

Every download the launcher makes is checked against the SHA-1 pinned in `research-lock.json`,
and the archive itself against `SHA256SUMS`.

## First-run warnings (the archives are unsigned)

- **Windows** — before extracting, right-click the `.zip` → **Properties** → tick **Unblock** →
  **Apply**. Then SmartScreen may still say "Windows protected your PC" for `Start Horizon.bat`'s
  programs: choose **More info** → **Run anyway**. The archive is signed by nobody; the checksum
  above is what proves it is intact.
- **macOS** — Gatekeeper blocks the first launch. Right-click `Horizon Launcher.command` →
  **Open** → **Open**. If it still refuses, run
  `xattr -dr com.apple.quarantine horizon-macos-arm64` once.

## On a 4 GB machine

Press Play and let it prepare; no compilation happens, so the memory a build needs is never
touched. The game still needs room to run: keep the render distance low (6–8 chunks) and close
other applications. The launcher's **Low-memory device** tick only affects building from source, so
it does nothing here.

## Limits

- Online-mode servers refuse this build by design; LAN and offline worlds work.
- Skins and capes need a Microsoft session and are not fetched.
- The macOS build is **Apple Silicon only**; Intel Macs must build from source.
- This release is built for Minecraft **26.3** and the same source commit as its tag. When the
  fork moves to another Minecraft version, a new release is needed.
- The game is in development; worlds are compatible with the source build of the same version,
  but back up anything you care about.

## If something goes wrong

- "Java not found" — install Java 25 with `javac`; the launcher names the path it looked for.
- "Minecraft 26.3 not found" — point **Browse…** at the folder your launcher installed it into.
- The window does not open — `./tools/launcher.sh --self-test` (Linux, macOS) or
  `py -3 tools\launcher.py --self-test` (Windows) prints what it found; the usual cause is a
  Python without tkinter.
- `Start Horizon.bat` closes instantly — open it from the extracted folder, not from inside the
  zip preview, and check the Python message above.
- The game is silent — preparation copies the sounds from your Minecraft install; tick **Copy
  the sounds** and press **Prepare game files**.
