# Forking: Horizon's extras and the vanilla game

Horizon is the vanilla game plus a few things of its own: cosmetics, Play with Friends, the
official server in the list, its settings pages. In the code they sit behind one Cargo feature,
`horizon-extras`, on by default, so a fork can build without them or delete them. Players always
get the full Horizon: there is no setting, flag or variable that turns the extras off.
Optimizations are not extras; they are part of the game in every build.

## Building without Horizon's extras

```sh
cargo build --release -p horizon-game --no-default-features --features audio,controllers
```

Best effort: CI builds and tests the default only. The server build (`--no-default-features`,
docs/server.md) compiles the same gates, so the code keeps compiling, but nobody plays it as a
client before a release. [horizon-rust/horizon-plain](https://github.com/horizon-rust/horizon-plain)
builds it, unsigned, from the newest dated Nightly that is at least a week old.

What changes in that build:

| Extra | Where it lives | The gate |
|---|---|---|
| Cosmetics, emotes and the emote wheel, "Show me as a Horizon player" | `game/cosmetics.rs` (+ `cosmetics/fx.rs`, `cosmetics/emotes.rs`, `cosmetics/emote_wheel.rs`), crate `horizon-cosmetics` | `game::cosmetics::enabled()`: the service is never asked, nothing is drawn, B opens no wheel |
| The official server added to the server list, the withdrawn partner server taken out; the "Start Horizon from the launcher" screen of a game without its prepared files, with its Download button (`get_the_game` hook) | crate `horizon-official-servers` | registered only by the official executable (`horizon-official`); horizon-client's own executable has none |
| Horizon Settings (Extras, PvP & HUD, Splitscreen, Studio, AI Agent) and Mods (with the registry browser) | `options_ui.rs` (`Page::Horizon` and below), `extras_ui.rs`, `extras.rs`, `pvp.rs`, `game/extras.rs` and `game/extras/`, `extras_hud.rs` | the Options screen shows vanilla's greyed Telemetry Data instead (`options_ui::HORIZON_EXTRAS`, set in `entry.rs`) |
| Discord Rich Presence and its switch | crate `horizon-discord` | registered only by the official executable (`horizon-official`); horizon-client's own executable has none |
| Play with Friends | hosting: `game/friends.rs`, `game/friends/screen.rs`; joining: crate `horizon-friends` (`game`) | hosting: the `friends` feature (`game/friends_off.rs` stands in); joining: only the official executable registers it ([layers.md](layers.md#how-a-horizon-crate-plugs-in)) |
| The anonymous "I'm playing" ping | crate `horizon-heartbeat` | not in horizon-client at all: only the official executable (`horizon-official`) registers it ([layers.md](layers.md#how-a-horizon-crate-plugs-in)) |

Credits & Attribution then says where the official build is (`horizon.plain.official`).

`grep -rn horizon-extras crates/` lists every gate. Apart from the `friends` feature above, the gates
are `cfg!(feature = "horizon-extras")`: both sides compile in every build, so no stub has to follow
the code it replaces. To remove an extra for good, delete its files from the table and the lines its
gate guards.

## Not behind the feature

- The launcher (`launcher/`) holds the Wardrobe, the Shop, the featured servers page, its themes,
  the telemetry consent and updates. A build of the game alone has none of them; without the
  launcher's consent the game keeps no crash or performance report (docs/telemetry.md).
- The graphics screen's fullbright, dynamic lights and hiding block-break particles: renderer
  options, off by default (docs/extras.md). A `horizon-extras.txt` left by an official install is
  still read.
- The mod runtime: nothing installs a mod without the launcher, so it stays idle.
- The `horizon` brand reply to a Horizon server, for its protocol extensions (`net.rs`).
- Agent control (`--control`, `horizon-ctl`), controllers, HDR, shader packs.

## Microsoft sign-in in a fork

Horizon's Microsoft sign-in runs under one Azure app registration, whose client ID release builds
read from the repository variable `HORIZON_MSA_CLIENT_ID` (docs/microsoft-account.md). That
registration, and Mojang's approval of it for the Minecraft services, are for Horizon's own builds
only. They do not pass to forks, ports or derived launchers, whatever their licence.

- A fork, port or derived launcher that signs players in registers its own Azure app and applies for
  its own approval from Mojang/Microsoft (the App ID review in docs/microsoft-account.md).
- Its builds must not ship, embed, download or otherwise fetch Horizon's client ID, and must not tell
  players to set `HORIZON_MSA_CLIENT_ID` to it. Sign-ins made with it would appear to Microsoft and
  Mojang as Horizon's, which the project does not accept.
- The MIT licence covers the code, not the app registration: copying the code gives no right to use
  Horizon's client ID.
- Horizon may restrict, rotate or revoke its client ID at any time, which breaks every build that
  uses it, and reports misuse to Microsoft, Mojang and the hosting platform.

A build made from source without a client ID of its own says that sign-in is not configured; that is
the expected state for a fork until its own app is approved.

## A fork that signs nobody in

This fork (arman0824/horizon) plays offline and never asks for a Microsoft account: no launcher
sign-in, no sign-in screen, no session hand-off. The reachable sign-in surface of the client was removed:

| Removed | Where it was |
|---|---|
| `--session-file PATH` and `--session-stdin`, and the `HORIZON_SESSION_FILE` variable, that handed the launcher's account to the game; the game now always plays as its offline profile (`--name`, `HORIZON_PLAYER_NAME`, or the name generated once into `horizon-player.txt`) | `game/runtime/launch_options.rs` (`Options::read`, `parse`, `--help`), `game/runtime/launch_api.rs` (the Launch API table), `docs/api/launch*.md` |
| `HORIZON_ACCOUNT_SESSIONS`, that gave splitscreen players their own signed-in account; split players are all offline now | `game/runtime/split/launcher.rs` |

What still works: single player, opening a world to LAN, joining servers in offline mode (`--server HOST`),
dedicated servers, `horizon-ctl`, mods, shader packs. What does not: joining a server in online mode (the
server refuses the player, as it would a vanilla client with no account), skins and profiles fetched from
the Minecraft services, the Play with Friends relay. Nothing in the build contacts Mojang, Microsoft or any
Horizon service; `auth::current()` has no producer, so every online path stays inert.

To build and play it (Rust 1.90+, JDK 25; Python 3.9+ for the launcher, 3.11+ for the harnesses):

```sh
./tools/launcher.sh    # pick your game files, press Play: builds, prepares (sounds included), plays
```

The build uses at most 8 parallel compiler jobs (`HORIZON_BUILD_JOBS=4 ./tools/launcher.sh` lowers
it) so a first build is less likely to be killed for memory; its log is `.local/logs/build-*.log`.
On a 4–8 GB machine, tick **Low-memory device** in the launcher: it builds with one job, one
front-end thread and `opt-level = 1` (`-Zthreads=1`, `-j1`), turns off incremental compilation, and
warns when the swap a first build needs is missing. Preparation runs one worker
(`HORIZON_PREPARE_JOBS=1`) and caps every exporter JVM at 1 GB (`HORIZON_PREPARE_HEAP=1G`), so a
step that outgrows the machine reports Java's OutOfMemoryError in the log instead of the session
being killed. The setting is remembered, and `./tools/launcher.sh --low-memory` does the same from a
terminal. A 4 GB machine is below any of this: it should not build the game at all.

### Prebuilt builds (Releases)

`.github/workflows/release.yml` builds one archive per platform on native GitHub-hosted runners:

| Job | Runner | Archive |
| --- | --- | --- |
| `linux` | `ubuntu-22.04` — the oldest glibc this project supports | `horizon-linux-x86_64.tar.gz` |
| `windows` | `windows-2022` (MSVC) | `horizon-windows-x86_64.zip` |
| `macos` | `macos-14` (Apple Silicon) | `horizon-macos-arm64.tar.gz` |

A `publish` job then collects the three, writes one `SHA256SUMS` covering all of them, checks that
no archive holds a `.jar`, a `minecraft/` directory or `.local/`, and creates the release once.
Every archive holds `target/fast/{horizon-client,horizon-prepare,horizon-ctl}` (`.exe` on Windows),
`tools/`, this lock file, the licence and the exporter sources; never Mojang's files, assets or
prepared resources. Windows gets `Start Horizon.bat` at the top level, macOS
`Horizon Launcher.command`; Linux keeps `tools/launcher.sh`.

It is for the machines that cannot build: a 4 GB laptop needs no Rust at all, just the archive.
Download, verify, unpack, open the launcher, press Play; the first Play still prepares the resources
from the player's own Minecraft, and Java 25 (with `javac`) is still needed for that, as is Python 3
with Tk for the window. In the launcher, **Download prebuilt** picks the archive for the running
machine, fetches and verifies it; `--download-prebuilt` does it from a terminal. The workflow runs
manually (Actions → fork release) and creates a draft first, so it can be inspected before
publishing.

The archives are unsigned. Windows SmartScreen and macOS Gatekeeper warn once; the release notes
tell the player what to click.

By hand, the launcher is a convenience over:

```sh
cargo build --profile fast -p horizon-game -p horizon-prepare
./target/fast/horizon-prepare --prepare --server-jar ~/Downloads/server.jar   # your own files; sounds too
./target/fast/horizon-client --resources .local/horizon-client/26.3
```

The game itself contacts nothing. The tools beside it reach Mojang only when asked: `horizon-prepare`
reads your own files, and `tools/launcher.py` downloads the pinned 26.3 server jar (and, when a
third-party launcher rewrote the version file, Mojang's own `26.3.json`), refusing anything whose
SHA-1 differs from `research-lock.json`. Neither signs anyone in.

`tools/test_online_mode_parity.py` (online-mode joins through a mock session service) cannot pass here and
is not run by this fork: it needs the session hand-off above.

This fork does not run upstream's automation either: `.github/workflows/` (27 workflows written for
horizon-rust's self-hosted runners, release train and bots), `.github/dependabot.yml`,
`.github/CODEOWNERS` and `.coderabbit.yaml` are not in the tree, so a push here starts nothing and no
reviewer or bot is asked for. The scripts under `tools/` stay, but only run when invoked by hand. A merge
from upstream tries to bring the workflows back: keep them deleted.
