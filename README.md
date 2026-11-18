<p align="center">
  <img src="docs/media/banner.webp" alt="Horizon: the game you know, rebuilt in Rust" width="100%">
</p>

# Play Minecraft: Java Edition 26.3 in Rust — offline, no account, no launcher

**Horizon** is Minecraft: Java Edition rewritten from scratch in Rust: one fast native program, no
Java, the same worlds and rules as the Java game. This fork removes all of the sign-in, so **the game
opens straight into a world as an offline player** — no Microsoft account, no launcher, no login
screen, and no internet check.

**Free, and ready if Minecraft is already on this machine.** Horizon is MIT-licensed and never checks
whether you paid for anything. It plays using the game files you already have — from the official
launcher **or any third-party launcher** (SKLauncher, TLauncher, Prism, MultiMC, ATLauncher, Modrinth
App, HMCL…). Nothing is downloaded and nothing is signed in to.

> You need: a Mac, Linux box or Windows PC, the game files from a launcher you already use, and the
> matching server jar (step 3). Everything else is free and open source. Not an official Minecraft
> product — see [the licence](#licence-and-credit).

---

# How to install it, step by step

Copy each block into a terminal, one step at a time. On macOS this takes about **10 minutes**, most
of it one automatic build. Windows and Linux work the same way.

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

## Step 3 — Get the server jar (one file, 62 MB)

Horizon builds the game's data from your client jar **and** the matching server jar. If your launcher
already has one, skip ahead. Otherwise:

- Open `~/Library/Application Support/minecraft/versions/26.3/26.3.json` (macOS) or
  `%APPDATA%\.minecraft\versions\26.3\26.3.json` (Windows), copy the URL after
  `"server": { "url": "` …
- …or just search `minecraft server 26.3 download` and use Mojang's own download page

Then check the file you downloaded, and put it somewhere permanent:

```sh
shasum -a 1 ~/Downloads/server.jar
# must print: 33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c
mkdir -p ~/Games && mv ~/Downloads/server.jar ~/Games/server.jar
```

## Step 4 — Build the game

```sh
~/.cargo/bin/cargo build --profile fast -p horizon-game -p horizon-prepare
```
About 5 minutes on Apple silicon; a binary lands in `target/fast/`.

## Step 5 — Turn your Minecraft files into the game's resources

```sh
./target/fast/horizon-prepare --prepare --server-jar ~/Games/server.jar
```

It looks for your game files by itself — `~/.minecraft` on Linux/Windows,
`~/Library/Application Support/minecraft` on macOS — or you name the folder:

```sh
./target/fast/horizon-prepare --prepare --minecraft-dir /path/to/.minecraft --server-jar ~/Games/server.jar
```

It copies nothing off your machine, downloads nothing, and asks for no account. It ends with
`Prepared Horizon native-client resources: …` (about 20 seconds).

### If step 5 fails with "is not a 26.3 version file Horizon knows"

That means your launcher (SKLauncher, TLauncher and friends) rewrites the version file, so its
checksum no longer matches. Fix it once — your launcher's folder is not touched:

```sh
mkdir -p .local/minecraft/26.3
curl -o .local/minecraft/26.3/manifest.json \
  https://piston-meta.mojang.com/v1/packages/11f1aefe473eefba0af62e3286c33b692807b2eb/26.3.json
shasum -a 1 .local/minecraft/26.3/manifest.json    # 11f1aefe473eefba0af62e3286c33b692807b2eb
./target/fast/horizon-prepare --prepare --server-jar ~/Games/server.jar
```

## Step 6 — Play

```sh
./tools/play-offline.sh
```

The window opens in seconds. **No account, no sign-in, nothing to click through.** Your worlds,
settings and player name live in `~/horizon-game/`, so they survive every rebuild.

Press **Esc** any time to open the menu; single player, LAN and offline-mode servers all work from
there.

Nice to know:

```sh
./tools/play-offline.sh --creative                 # creative mode
./tools/play-offline.sh --seed 1234                # a world of your own seed
./tools/play-offline.sh --world "New World"        # open a world you already had
./tools/play-offline.sh --name Steve               # your own player name
./target/fast/horizon-client --help                # every option
```

### Optional: sound

The game starts silent. To copy vanilla sounds (~380 MB) from your install, once:

```sh
./target/fast/horizon-prepare sounds
```

---

# What this fork changed, and what it costs

One commit (`6b82ad3`) removes the sign-in surface and nothing else:

- `--session-file`, `--session-stdin`, `HORIZON_SESSION_FILE` — how a signed-in account was handed
  to the game. They are now refused as unknown options.
- `HORIZON_ACCOUNT_SESSIONS` — how splitscreen players signed in.
- The Microsoft sign-in and the launcher are not part of the build at all.

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
| `is not a 26.3 version file Horizon knows` | Step 5's fix, above |
| `No 26.3 server jar` | Give it `--server-jar PATH` (step 3) |
| `prepared game files are missing` | Run step 5, or pass `--resources .local/horizon-client/26.3` |
| `--session-file: unknown option` | Expected — this fork signs nobody in |
| A server refuses you with `invalidSession` | It is in online mode; this fork cannot join it |
| The game is quiet | `horizon-prepare sounds` |
| Items missing in an old modded world | The mod's files weren't present at step 5 |

# Licence and credit

Horizon is MIT-licensed, © Ludovic Marie and [its contributors](https://github.com/horizon-rust/horizon/graphs/contributors);
this fork keeps that licence and attribution. Horizon contains no Mojang code and no Mojang assets:
it reads the game files you already have, prepares them on your own machine into `.local/`, and never
copies them anywhere else. You must have the game files from a launcher you already use.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
Minecraft is a trademark of Mojang Synergies AB; its code and assets belong to Mojang and Microsoft
under the [Minecraft EULA](https://www.minecraft.net/en-us/eula).
