<p align="center">
  <img src="docs/media/banner.webp" alt="Horizon: the game you know, rebuilt in Rust" width="100%">
</p>

<p align="center">
  <a href="https://github.com/horizon-rust/horizon"><b>Upstream project</b></a> ·
  <a href="docs/forking.md"><b>This fork</b></a> ·
  <a href="#play-in-three-steps"><b>Play</b></a> ·
  <a href="ROADMAP.md"><b>Roadmap</b></a>
</p>

# Horizon — Minecraft: Java Edition 26.3 in Rust, offline, no account

**Minecraft: Java Edition 26.3, rewritten from scratch in Rust.** One native program — no Java at
runtime — with the same worlds, the same rules and the same terrain as the Java game, checked against
vanilla by hundreds of differential tests. Free, open source (MIT) and unofficial: you play it with
your own copy of the game's files.

> **This fork ([arman0824/horizon](https://github.com/arman0824/horizon)) has no login and no auth at all.**
> No launcher, no Microsoft sign-in, no session hand-off, no token, no consent flow: the game starts
> straight into a world as an offline player. **If Minecraft is already installed on this machine —
> from the official launcher *or* any third-party launcher (SKLauncher, TLauncher, Prism, MultiMC,
> ATLauncher, Modrinth App, HMCL …) — you already have everything this needs.** Nothing is downloaded,
> nothing is verified against an account, and nothing is ever signed in to.

## Why there is no sign-in, and what that changes

In the official build the account does three things: it proves you own the game (the launcher's
gate), it gives the game skins, chat keys and a profile, and it lets you join servers running in
*online mode*. This fork removes all of it:

| Removed | What it was |
| --- | --- |
| `--session-file PATH`, `--session-stdin`, `HORIZON_SESSION_FILE` | How the launcher handed your signed-in account to the game. Now refused as unknown options. |
| `HORIZON_ACCOUNT_SESSIONS` | How splitscreen players each signed in. Split players are offline too. |
| The launcher workspace | Not built, not needed. This repository builds the engine only. |

Nothing in the fork can sign in, because nothing produces an account: `auth::current()` has no
producer left, so every online path — the Minecraft services' session server, skin and profile
lookups, chat keys, the friends relay — stays inert. The engine is untouched Rust: worldgen,
physics, rendering (wgpu/Metal/Vulkan), netcode and saves all work exactly as upstream.

What still works: single player, creating and upgrading worlds, opening a world to **LAN**, joining
servers that run in **offline mode** (`--server HOST`), the dedicated server, `horizon-ctl`, content
mods, resource packs, shader packs.

What does not: joining a server in **online mode** (it refuses you, exactly as it would a vanilla
client started with no account), skins/profiles fetched from Mojang, Play with Friends. Details:
[docs/forking.md](docs/forking.md).

## Play in three steps

### 0. What you need

- This repository, and Rust 1.90+ (built and tested on 1.100): `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- Python 3.11+ and **JDK 25** — only for the one-time `horizon-prepare` step below (it runs vanilla's
  exporters over your own jars to extract the game's data; no Java ever runs when you play)
- Your Minecraft install, with the version's **client jar, assets and libraries** — from any launcher,
  third-party included. `horizon-prepare` finds it automatically (`~/.minecraft` on Linux/Windows,
  `~/Library/Application Support/minecraft` on macOS), or name it with `--minecraft-dir PATH`
- The **matching server jar** for the same version — Horizon prepares the server side from it. Get it
  from your version's `versions/<version>/<version>.json` (`downloads.server.url`) or
  [minecraft.net/download](https://www.minecraft.net/en-us/download/server):

```sh
shasum -a 1 server.jar     # must equal the server_sha1 pin in research-lock.json
```

### 1. Build the engine

```sh
git clone https://github.com/arman0824/horizon.git
cd horizon
cargo build --profile fast -p horizon-client -p horizon-prepare     # ~5 min on Apple silicon
```

### 2. Prepare the game's data from your own files

```sh
./target/fast/horizon-prepare --prepare --server-jar /path/to/server.jar
```

It imports and checks your jars and assets against the pins in `research-lock.json`, then writes
the prepared resources to `.local/horizon-client/26.3` (gitignored, ~730 MB). It never downloads
Mojang's files — it reads the ones you already have.

> **Third-party launcher?** SKLauncher, TLauncher and friends rewrite your version JSON, so
> `horizon-prepare` refuses it (`… is not a 26.3 version file Horizon knows`). Save Mojang's own copy
> once and prepare again — your launcher's folder is not touched:
> ```sh
> curl -o .local/minecraft/26.3/manifest.json \
>   https://piston-meta.mojang.com/v1/packages/11f1aefe473eefba0af62e3286c33b692807b2eb/26.3.json
> shasum -a 1 .local/minecraft/26.3/manifest.json   # 11f1aefe…
> ```
> (Only game *files* — jars, assets, libraries — come from your launcher; the manifest is public
> metadata, and its SHA-1 must match the pin or prepare stops.)

### 3. Play

```sh
./tools/play-offline.sh                    # saves, options and your name go in ~/horizon-game
```

or run the game directly:

```sh
./target/fast/horizon-client --game-dir ~/horizon-game --home ~/horizon-game
```

You are in the game in a couple of seconds, as an offline player — no window ever asks for an
account. Your name is generated once and kept in `~/horizon-game/horizon-player.txt`; pick your own
with `--name Steve`.

Useful flags: `--creative`, `--seed 1234`, `--world "New World"` (opens an existing save, including
one made in any launcher — Horizon upgrades worlds from 1.8 to 26.2 itself), `--render-distance 32`,
`--server HOST[:PORT]` (offline-mode servers), `--fullscreen`, `--help` for everything.

## Everything we changed

One commit, `6b82ad3` "Fork: play offline, with no Microsoft sign-in":

- `crates/horizon-client/src/game/launch_options.rs` — dropped the session hand-off (`--session-file`,
  `--session-stdin`, `HORIZON_SESSION_FILE`), the fields and the `--help` text; the game always uses
  its offline profile
- `crates/horizon-client/src/game/launch_api.rs` — the Launch API no longer advertises the session
  options (`--launch-api` prints the truth)
- `crates/horizon-client/src/game/split/launcher.rs` — `HORIZON_ACCOUNT_SESSIONS` reads nothing, so
  no session file is ever opened, consumed or deleted
- `docs/api/launch*.md`, `docs/forking.md`, this README
- The launcher workspace (`launcher/`) is simply never built; the fork builds the engine only

Nothing else was touched: no gameplay, rendering, worldgen or save code changed, so vanilla parity
and the upstream differential harnesses stay valid. (`tools/test_online_mode_parity.py` needs the
removed hand-off and cannot pass in this fork; it is not run.)

Verified on a MacBook Air before the fork was published, headlessly and with a real window: resources
prepared from a third-party launcher's own jars, a new world generated and ticked for five minutes
with saves written, and an existing 84 MB vanilla save reopened at its real spawn point — with no
JVM process and no auth line anywhere in the logs.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `… is not a 26.3 version file Horizon knows` | Your launcher rewrote the version JSON — see step 2 |
| `No 26.3 server jar…` | Pass `--server-jar PATH` (or set `HORIZON_SERVER_JAR`); the SHA-1 must match `research-lock.json` |
| `Horizon's prepared game files are missing` | Run step 2, or pass `--resources .local/horizon-client/26.3` |
| No sound | `./target/fast/horizon-prepare sounds` copies ~380 MB from your install (optional) |
| Missing items after opening a modded save | The mod's data wasn't imported; re-run prepare with the mod's jars present |
| `--session-file: unknown option` | Expected: this fork signs nobody in |
| A server says `disconnect.loginFailedInfo.invalidSession` | That server is in online mode — this fork cannot join it |

## Rebuilding and updating

```sh
cd ~/Desktop/horizon
~/.cargo/bin/cargo build --profile fast -p horizon-client    # after any local edit; ~5 min cold, seconds warm
./target/fast/horizon-prepare --check                        # resources still current for this build
```

Merging upstream: `git fetch upstream && git merge upstream/main` resolves the sign-in removal cleanly
(it is a small, self-contained diff). Rebuild, prepare, play.

## Licence and credit

MIT for the project's original work, © Horizon's contributors, Ludovic Marie and
[its contributors](https://github.com/horizon-rust/horizon/graphs/contributors) — the attribution and
licence above remain in force for this fork. Horizon contains no Mojang code or assets: it reads the
game files you already own, and prepares them into `.local/` locally, never redistributing them.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
Minecraft is a trademark of Mojang Synergies AB; its code and assets belong to Mojang and Microsoft
under the [Minecraft EULA](https://www.minecraft.net/en-us/eula).
