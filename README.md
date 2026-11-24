<p align="center">
  <img src="docs/media/banner.webp" alt="Horizon: the game you know, rebuilt in Rust" width="100%">
</p>

# Minecraft: Java Edition 26.3 in Rust — offline, no account

**Horizon** is Minecraft: Java Edition rewritten in Rust: one native program, no Java while you
play, the same worlds and rules. This fork removes sign-in entirely, so the game opens as an offline
player — no Microsoft account, no login screen, no session, no internet check.

It reads the Minecraft files you already have, from the official launcher or any third-party one
(Prism, MultiMC, SKLauncher, TLauncher, ATLauncher, Modrinth App, HMCL…). Nothing is signed in. The
only thing it downloads from Mojang is the matching server jar, and only when it is not already on
the machine.

Not an official Minecraft product — see [Licence](#licence).

## Requirements

| | Needed for | Version |
| --- | --- | --- |
| **Minecraft: Java Edition** | The game files to prepare | 26.3, installed once by any launcher |
| **Java** | Preparing resources, once | JDK 25 with `javac` |
| **Python 3 + tkinter** | The launcher window | Any current Python 3 |
| **Rust** | Building from source only | 1.95 or newer |

Java is not used to play. The prebuilt archives need no Rust.

## Install

### Option A — Prebuilt archive (no compiler)

Download the archive for your machine **and `SHA256SUMS`** from
[Releases](https://github.com/arman0824/horizon/releases/latest):

| Machine | Archive |
| --- | --- |
| Linux x86_64 | `horizon-linux-x86_64.tar.gz` |
| Windows x86_64 | `horizon-windows-x86_64.zip` |
| Apple Silicon Mac (M1 and later) | `horizon-macos-arm64.tar.gz` |

Then, in order:

**1. Check the download.** In the folder holding both files:

```sh
sha256sum -c SHA256SUMS --ignore-missing       # Linux
shasum -a 256 -c SHA256SUMS --ignore-missing   # macOS
```

```powershell
# Windows: the printed hash must match the zip's line in SHA256SUMS
Get-FileHash .\horizon-windows-x86_64.zip -Algorithm SHA256
```

Every downloaded archive must print `OK` (or match its line in `SHA256SUMS`).

**2. Extract it** to a folder you keep (for example `~/Games/horizon`):

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

The launcher's **Download prebuilt** button does the same thing from inside the app: it picks this
machine's archive, verifies its SHA-256 and installs the programs.

### Option B — Build from source

Install the tools:

```sh
# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
. "$HOME/.cargo/env"

# JDK 25 — macOS
brew install openjdk@25

# JDK 25 — Debian/Ubuntu
sudo apt install openjdk-25-jdk
```

Windows: [rustup-init.exe](https://rustup.rs) and [Temurin 25](https://adoptium.net/?specification=25).

Then clone and open the launcher:

```sh
git clone https://github.com/arman0824/horizon.git
cd horizon
./tools/launcher.sh
```

```bat
:: Windows
tools\launcher.bat
```

## First Play

The window finds Minecraft automatically; use **Browse…** if it does not. Press **Play**:

1. **Builds the game** (5–15 minutes; skipped in the prebuilt archives).
2. **Finds or downloads** the 26.3 server jar (62 MB, checked against the SHA-1 in
   `research-lock.json`).
3. **Prepares the game files and copies the sounds**, so the game is not silent.
4. **Opens the game.** No account, no sign-in, nothing to click through.

Later Plays start in seconds and repair only what changed.

| Launcher field | What it does |
| --- | --- |
| **Minecraft folder** | Where your launcher installed Minecraft; found automatically |
| **Server file** | The 26.3 `server.jar`, read once to build the game's data |
| **Worlds & settings** | Saves, `options.txt`, player name and logs (default `~/horizon-game`) |
| **Copy the sounds too** | On by default, about 380 MB from your own files; off means silence |
| **Low-memory device** | One compiler job and a 1 GB Java heap for 4–8 GB machines; on automatically below 8 GB |
| **Download prebuilt** | Installs this machine's release archive, no compilation |
| **Prepare game files** | Runs preparation again |
| **Play** | Builds and prepares if needed, then starts the game |

## Terminal instead of the launcher

The launcher does the same work as these commands:

```sh
cargo build --profile fast -p horizon-game -p horizon-prepare
./target/fast/horizon-prepare --prepare --server-jar ~/Downloads/server.jar   # sounds included
./tools/play-offline.sh
```

`--no-sounds` skips the sounds; `--complete` also fails if anything is still missing.

```sh
./tools/play-offline.sh --creative               # creative mode
./tools/play-offline.sh --seed 1234              # a chosen seed
./tools/play-offline.sh --world "New World"      # an existing world
./tools/play-offline.sh --name Steve             # a chosen player name
./target/fast/horizon-client --help              # every option
```

If a third-party launcher rewrote Minecraft's version file, the launcher notices and downloads
Mojang's own `26.3.json` automatically. By hand:

```sh
mkdir -p .local/minecraft/26.3
curl -o .local/minecraft/26.3/manifest.json \
  https://piston-meta.mojang.com/v1/packages/11f1aefe473eefba0af62e3286c33b692807b2eb/26.3.json
shasum -a 1 .local/minecraft/26.3/manifest.json   # 11f1aefe473eefba0af62e3286c33b692807b2eb
```

## What this fork changes

One commit (`6b82ad3`) removes the sign-in surface and nothing else:

- `--session-file`, `--session-stdin` and `HORIZON_SESSION_FILE` are refused as unknown options.
- `HORIZON_ACCOUNT_SESSIONS` is gone; split-screen players are offline too.
- The Microsoft sign-in and upstream's launcher are not built.

The engine is untouched, so vanilla's differential tests keep their meaning. You get single player,
LAN worlds, offline-mode servers, content mods, resource and shader packs, `horizon-ctl`, and a
start with no account round-trip.

**Limits:** online-mode servers refuse this build, Mojang skins and capes do not load, and Play with
Friends is unavailable. None of that changes how the game plays.

Details: [docs/forking.md](docs/forking.md) · upstream: [horizon-rust/horizon](https://github.com/horizon-rust/horizon)

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `is not a 26.3 version file Horizon knows` | Your launcher rewrote it; Horizon downloads Mojang's copy automatically |
| `No 26.3 server jar` | The launcher downloads it; by hand, pass `--server-jar PATH` |
| `prepared game files are missing` | Press **Play**, or run the terminal commands above |
| `--session-file: unknown option` | Expected — this fork signs nobody in |
| A server refuses you with `invalidSession` | It is online-mode; this fork cannot join it |
| The window does not open | `./tools/launcher.sh --self-test` (Linux/macOS) or `py -3 tools\launcher.py --self-test` (Windows) names the cause; usually Python without tkinter |
| The build is killed / `Killed` | Out of memory. On 4 GB, use the prebuilt archive. On 6–8 GB, tick **Low-memory device** and retry. Logs: `.local/logs/build-*.log` |
| The game is silent | Run `./target/fast/horizon-prepare sounds` from the repo root, or re-prepare with **Copy the sounds** ticked |
| Items missing in a modded world | The mod's files were not present when you prepared |

## Licence

Horizon is MIT-licensed, © Ludovic Marie and [its contributors](https://github.com/horizon-rust/horizon/graphs/contributors);
this fork keeps that licence and attribution. It contains no Mojang code or assets: it reads the
files you already have and prepares them locally into `.local/`.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
Minecraft is a trademark of Mojang Synergies AB; its code and assets belong to Mojang and Microsoft
under the [Minecraft EULA](https://www.minecraft.net/en-us/eula).
