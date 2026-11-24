<p align="center">
  <img src="docs/media/banner.webp" alt="Horizon: the game you know, rebuilt in Rust" width="100%">
</p>

# Play Minecraft: Java Edition 26.3 in Rust — offline, no account, no sign-in

**Horizon** is Minecraft: Java Edition rewritten from scratch in Rust: one fast native program, no
Java, the same worlds and rules as the Java game. This fork removes all of the sign-in, so **the game
opens straight into a world as an offline player** — no Microsoft account, no login screen, no
session, and no internet check.

**Free, and ready if Minecraft is already on this machine.** Horizon is MIT-licensed and never checks
whether you paid for anything. It plays using the game files you already have — from the official
launcher **or any third-party launcher** (SKLauncher, TLauncher, Prism, MultiMC, ATLauncher, Modrinth
App, HMCL…). Nothing is signed in to; the only thing the launcher fetches is Mojang's matching
server file, and only when it is not already on your machine.

> You need: a Mac, Linux box or Windows PC, and the game files from a launcher you already use.
> The matching server file is fetched and checked for you (step 3). Everything else is free and open
> source. Not an official Minecraft product — see [the licence](#licence-and-credit).

---

# How to install it, step by step

Three steps. The launcher does the rest, including the sounds, with no account anywhere. On macOS
the first run takes about **10 minutes**, most of it one automatic build. Windows and Linux work the
same way.

## Step 1 — Get the code

**macOS and Linux:**
```sh
git clone https://github.com/arman0824/horizon.git
cd horizon
```

**Windows** (PowerShell):
```powershell
git clone https://github.com/arman0824/horizon.git
cd horizon
```

## Step 2 — Install the two build tools

You need **Rust** (the language the game is written in) and **JDK 25** (used once, to read your
Minecraft files; no Java runs when you play).

**Rust** — macOS/Linux:
```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
. "$HOME/.cargo/env"
rustc --version        # 1.90 or newer
```
Windows: download and run [rustup-init.exe](https://rustup.rs), then reopen the terminal.

**JDK 25** —
```sh
# macOS (Homebrew)
brew install openjdk@25
java -version          # "openjdk version \"25...\""
```
Linux: `sudo apt install openjdk-25-jdk` (or your distro's equivalent).
Windows: install [Temurin 25](https://adoptium.net/?specification=25) or any JDK 25.

### No compiler? Download the Linux build

A 4-8 GB ram machine cannot compile this project; it does not have to. The fork publishes a prebuilt
**Linux x86_64** build on
[Releases](https://github.com/arman0824/horizon/releases/latest): download
`horizon-linux-x86_64.tar.gz`, check it against `SHA256SUMS`, unpack it wherever you like, and run
`./tools/launcher.sh` inside. The launcher sees the programs and skips the build entirely — the
steps below are the same from **Play** onward. This needs Rust nowhere on the machine; Java is still
used once, to prepare the resources.

In the launcher window, **Download prebuilt** does the same thing without leaving the app. It
fetches the archive, checks its SHA-256 and installs the three programs; on macOS and Windows the
button is disabled because no prebuilt build is published for them yet.

## Step 3 — Open the launcher

```sh
./tools/launcher.sh
```

A window opens, already knowing where Minecraft is. Press **Play** — that is the whole thing:

1. The first run **builds the game** (5–15 minutes; the window shows the compiler's progress).
2. It **finds the matching server file** on your machine, or downloads it from Mojang once (62 MB,
   checked against the SHA-1 pinned in `research-lock.json`).
3. It **prepares your game files and copies the sounds**, so the game is not silent.
4. The game opens. **No account, no sign-in, nothing to click through.**

Later runs start in seconds: **Play** re-checks the prepared files and repairs only what changed.

| In the launcher | What it is for |
| --- | --- |
| **Minecraft folder** | Where your launcher installed Minecraft. Found automatically; **Browse…** if you use SKLauncher, TLauncher, Prism, MultiMC… |
| **Server file** | The 26.3 `server.jar`, read once to build the game's data. Found or downloaded; **Browse…** to use your own copy |
| **Worlds & settings** | Saves, `options.txt`, player name and logs (default `~/horizon-game`) |
| **Copy the sounds too** | On by default, about 380 MB from your own game files; off means a silent game |
| **Low-memory device** | For 4–8 GB machines: builds with one compiler job, one front-end thread and lower optimisation, and prepares with one worker and a 1 GB Java heap, so neither the first build nor the preparation takes the session down. Ticked automatically below 8 GB |
| **Download prebuilt** | Linux x86_64 only: fetches the release's programs (about 75 MB), checks their SHA-256 and installs them, so nothing is compiled. Disabled once the game is built |
| **Prepare game files** | Runs the preparation again by hand |
| **Play** | Builds and prepares if needed, then starts the game |

## Step 4 — Nothing else

There is no sign-in step, no account to create and no launcher service to connect to. If the game
window is open, you are done.

### If your launcher rewrote Minecraft's version file

Third-party launchers (SKLauncher, TLauncher and friends) edit the version file, so its checksum no
longer matches the one Horizon pins. The launcher notices this, downloads Mojang's own `26.3.json`,
checks it and prepares again — you do not have to do anything. By hand, it is:

```sh
mkdir -p .local/minecraft/26.3
curl -o .local/minecraft/26.3/manifest.json \
  https://piston-meta.mojang.com/v1/packages/11f1aefe473eefba0af62e3286c33b692807b2eb/26.3.json
shasum -a 1 .local/minecraft/26.3/manifest.json    # 11f1aefe473eefba0af62e3286c33b692807b2eb
```

---

# Play without the launcher (terminal only)

The launcher is a convenience over these commands; they do exactly the same work.

```sh
# 1. The server jar (skip when a previous run kept it)
shasum -a 1 ~/Downloads/server.jar
# must print: 33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c
mkdir -p ~/Games && mv ~/Downloads/server.jar ~/Games/server.jar

# 2. Build the game
~/.cargo/bin/cargo build --profile fast -p horizon-game -p horizon-prepare

# 3. Prepare your Minecraft files — the sounds are copied too
./target/fast/horizon-prepare --prepare --server-jar ~/Games/server.jar

# 4. Play
./tools/play-offline.sh
```

`horizon-prepare --prepare` ends with `Prepared Horizon native-client resources: …` and
`Sound assets ready: 4962 files, 377.3 MB` (about 20 seconds). `--no-sounds` leaves the sounds out;
`--complete` also fails unless nothing is missing afterwards.

The sounds land in `.local/horizon-client/26.3/assets/minecraft/sounds/`, the folder
`./tools/play-offline.sh` passes as `--resources`. If you prepare into another folder with
`--output`, pass the same `--output` there. A silent game from an older clone is repaired with
`./target/fast/horizon-prepare sounds` (run from the repo root).

Nice to know:

```sh
./tools/play-offline.sh --creative                 # creative mode
./tools/play-offline.sh --seed 1234                # a world of your own seed
./tools/play-offline.sh --world "New World"        # open a world you already had
./tools/play-offline.sh --name Steve               # your own player name
./target/fast/horizon-client --help                # every option
```

---

# What this fork changed, and what it costs

One commit (`6b82ad3`) removes the sign-in surface and nothing else:

- `--session-file`, `--session-stdin`, `HORIZON_SESSION_FILE` — how a signed-in account was handed
  to the game. They are now refused as unknown options.
- `HORIZON_ACCOUNT_SESSIONS` — how splitscreen players signed in.
- The Microsoft sign-in and upstream's launcher are not part of the build at all; the offline
  launcher in `tools/` only starts the game and downloads no account.

The engine itself — world generation, physics, rendering, netcode, saving — is untouched, so all of
vanilla's differential tests still mean what they meant upstream.

This buys you: single player, LAN worlds, offline-mode servers, content mods, resource and shader
packs, the `horizon-ctl` scripting interface, and a startup with no account round-trip at all.

It costs you: **servers in online mode will refuse you** (they require a real Microsoft session),
skins don't load from Mojang, and Play with Friends is out. None of that touches how the game plays.

Full details: [docs/forking.md](docs/forking.md) · upstream project:
[horizon-rust/horizon](https://github.com/horizon-rust/horizon)

# Troubleshooting

| What you see | What to do |
| --- | --- |
| `is not a 26.3 version file Horizon knows` | Your launcher rewrote it; the launcher's fix is above |
| `No 26.3 server jar` | The launcher downloads it; by hand pass `--server-jar PATH` |
| `prepared game files are missing` | Press **Play** (it prepares), or run the terminal block above |
| `--session-file: unknown option` | Expected — this fork signs nobody in |
| A server refuses you with `invalidSession` | It is in online mode; this fork cannot join it |
| The first build is killed, or the terminal says `/bin/fish crashed` / `Killed` | The system ran out of memory while compiling. On a 4 GB machine, stop building: download the prebuilt Linux build (above) and press Play. On 6–8 GB, tick **Low-memory device** and press Play again; adding a 16 GB swap file first helps. The full log is in `.local/logs/build-*.log`. |
| The game is quiet | `--prepare` copies the sounds by default, so this is usually an old prepared folder: run `./target/fast/horizon-prepare sounds` **from the repo root** (it writes into the folder `--resources` names). No `Horizon: audio output …` line in `logs/latest.log` means the OS never gave the game a device. |
| Items missing in an old modded world | The mod's files weren't present when you prepared |

# Licence and credit

Horizon is MIT-licensed, © Ludovic Marie and [its contributors](https://github.com/horizon-rust/horizon/graphs/contributors);
this fork keeps that licence and attribution. Horizon contains no Mojang code and no Mojang assets:
it reads the game files you already have, prepares them on your own machine into `.local/`, and never
copies them anywhere else. You must have the game files from a launcher you already use.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
Minecraft is a trademark of Mojang Synergies AB; its code and assets belong to Mojang and Microsoft
under the [Minecraft EULA](https://www.minecraft.net/en-us/eula).
