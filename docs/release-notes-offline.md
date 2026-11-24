# Horizon 26.3 — offline build for Linux, Windows and macOS

Minecraft: Java Edition 26.3 rewritten in Rust. **No account, no sign-in, no compiler.** Each
archive holds the finished programs, so nothing is built on your machine.

| Machine | Archive |
| --- | --- |
| Linux x86_64 (glibc 2.35 and newer) | `horizon-linux-x86_64.tar.gz` |
| Windows x86_64 | `horizon-windows-x86_64.zip` |
| Apple Silicon Mac (M1 and later) | `horizon-macos-arm64.tar.gz` |

## Install

Download the archive for your machine **and `SHA256SUMS`**, then:

**1. Check the download.** In the folder holding both files:

```sh
sha256sum -c SHA256SUMS --ignore-missing       # Linux
shasum -a 256 -c SHA256SUMS --ignore-missing   # macOS
```

```powershell
# Windows: the printed hash must match the zip's line in SHA256SUMS
Get-FileHash .\horizon-windows-x86_64.zip -Algorithm SHA256
```

**2. Extract it** to a folder you keep:

```sh
tar xzf horizon-linux-x86_64.tar.gz      # Linux
tar xzf horizon-macos-arm64.tar.gz       # macOS (or double-click it in Finder)
```

**Windows:** right-click the `.zip` → **Properties** → tick **Unblock** → **Apply**, then
**Extract All** and open the extracted folder. Do not run anything from the zip preview.

**3. Open the launcher** from inside the extracted folder:

| Machine | Do this |
| --- | --- |
| Linux | `./tools/launcher.sh` |
| macOS | double-click `Horizon Launcher.command` |
| Windows | double-click `Start Horizon.bat` |

The Windows and macOS archives are unsigned, so each asks once:

- **macOS:** right-click `Horizon Launcher.command` → **Open** → **Open**. If it still refuses, run
  `xattr -dr com.apple.quarantine horizon-macos-arm64` in Terminal once.
- **Windows:** SmartScreen says "Windows protected your PC" → **More info** → **Run anyway**.

**4. Press Play.** The window finds Minecraft automatically; the first Play prepares the game files.

## What you need

- **Minecraft 26.3 installed once** by any launcher (official, Prism, MultiMC, SKLauncher…), or that
  `.minecraft` folder copied over. You must own the game.
- **Java 25 with `javac`** for the preparation step: it compiles Horizon's exporter classes from the
  sources in the archive, about 20 seconds, once. Linux: `openjdk-25-jdk`; macOS:
  `brew install openjdk@25`; Windows: [Temurin 25](https://adoptium.net/?specification=25).
- **Python 3 with tkinter** for the window. Linux: `python3-tk`; macOS: the system Python, or
  `brew install python-tk`; Windows: the python.org installer with "tcl/tk and IDLE" ticked.
- **No Rust.** The archives are prebuilt.

## What is in the archive

```
horizon-linux-x86_64/          (macOS and Windows: same layout)
  target/fast/horizon-client      the game        (.exe on Windows)
  target/fast/horizon-prepare     reads your Minecraft files
  target/fast/horizon-ctl         command-line control (optional)
  tools/launcher.sh               the window      (Windows: Start Horizon.bat)
  tools/launcher.py                               (macOS: Horizon Launcher.command)
  tools/play-offline.sh           the same thing in a terminal (Linux, macOS)
  mods/horizon/src/test/java/     exporter sources, compiled once on first prepare
  research-lock.json              the Minecraft 26.3 files it checks
  README.md, LICENSE, LICENSES/
```

It does **not** contain Minecraft's jars, assets or sounds, and it cannot: those are Mojang's
files. The launcher reads the copy you already own and prepares the game's resources from it. The
game itself never runs Java.

Every download the launcher makes is checked against the SHA-1 pinned in `research-lock.json`, and
the archive against `SHA256SUMS`.

## First Play

1. **Builds the game** — skipped here; the programs are prebuilt.
2. **Finds or downloads** the 26.3 server jar (62 MB, SHA-1 checked).
3. **Prepares the game files and copies the sounds**, so the game is not silent.
4. **Opens the game.** No account, no sign-in, nothing to click through.

Later Plays start in seconds and repair only what changed.

## On a 4 GB machine

Use the prebuilt archive: nothing compiles, so the memory a build needs is never touched. Keep the
render distance low (6–8 chunks) and close other applications. The launcher's **Low-memory device**
tick only affects building from source.

## Limits

- Online-mode servers refuse this build by design; LAN and offline worlds work.
- Skins and capes need a Microsoft session and are not fetched.
- The macOS build is **Apple Silicon only**; Intel Macs must build from source.
- This release is for Minecraft **26.3** and the source commit at its tag. A new Minecraft version
  needs a new release.
- Worlds are compatible with the source build of the same version, but back up anything you care
  about.

## If something goes wrong

- "Java not found" — install Java 25 with `javac`; the launcher names the path it looked for.
- "Minecraft 26.3 not found" — point **Browse…** at the folder your launcher installed it into.
- The window does not open — `./tools/launcher.sh --self-test` (Linux, macOS) or
  `py -3 tools\launcher.py --self-test` (Windows) prints what it found; usually Python without
  tkinter.
- `Start Horizon.bat` closes instantly — run it from the extracted folder, not the zip preview.
- The game is silent — tick **Copy the sounds** and press **Prepare game files**.

Full instructions, launcher options and terminal commands: the repository's `README.md`.
