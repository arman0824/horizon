# Horizon 26.3 — offline Linux build

Minecraft: Java Edition 26.3 rewritten in Rust, for Linux x86_64. **No account, no sign-in,
no compiler.** This archive holds the finished programs, so nothing has to be built on your
machine.

## What is in the archive

```
horizon-linux-x86_64/
  target/fast/horizon-client      the game
  target/fast/horizon-prepare     reads your own Minecraft files
  target/fast/horizon-ctl         command-line control (optional)
  tools/launcher.sh               the window
  tools/launcher.py
  tools/play-offline.sh           the same thing in a terminal
  mods/horizon/src/test/java/     the exporter sources, compiled once on first prepare
  research-lock.json              the Minecraft 26.3 files it checks
  README.md, LICENSE, LICENSES/
```

It does **not** contain Minecraft's jars, assets or sounds, and it cannot: those are Mojang's
files. The launcher reads the copy you already own and prepares the game's resources from it.
The game itself never runs Java; Java is used once, during preparation.

## What you need

- Linux x86_64 (any current distribution; the build targets glibc 2.35 and newer).
- **Minecraft 26.3 installed once** by any launcher (official, Prism, MultiMC…), or that
  `.minecraft` folder copied over. You must own the game.
- **Java 25 with `javac`** for the preparation step: `sudo pacman -S jdk-openjdk` on Arch/CachyOS,
  `sudo apt install openjdk-25-jdk` on Debian/Ubuntu. Check with `java -version` and
  `javac -version`. The first preparation compiles Horizon's exporter classes from the sources in
  the archive — about 20 seconds, once.
- **Python 3 with tkinter** for the window: `sudo pacman -S python tk` (most systems have it).
- ALSA and a working Vulkan driver, as for any Linux game.

## Install and play

```sh
sha256sum -c SHA256SUMS --ignore-missing
tar xzf horizon-linux-x86_64.tar.gz
cd horizon-linux-x86_64
./tools/launcher.sh
```

In the window: check **Minecraft folder** (found automatically; **Browse…** if not), leave
**Copy the sounds** on, press **Play**. The first Play prepares the game files from your
Minecraft copy — a few minutes — and opens the game. Later Plays start immediately.

Without a window: `./tools/play-offline.sh` after preparing once with
`./target/fast/horizon-prepare --prepare --server-jar /path/to/server.jar`.

Every download the launcher makes is checked against the SHA-1 pinned in `research-lock.json`,
and the archive itself against `SHA256SUMS`.

## Mods, shader packs and resource packs

The launcher has **Add mod…**, **Add shader pack…**, **Add resource pack…** and **Installed
mods…**. They copy files into the game folder and turn content mods on; picking a shader or
resource pack stays in game (**Options → Horizon Settings → Shader Packs**, **Options → Resource
Packs**). Fabric and NeoForge jars do not run: they need Java, which Horizon does not use.

## On a 4 GB machine

Press Play and let it prepare; no compilation happens, so the memory a build needs is never
touched. The game still needs room to run: keep the render distance low (6–8 chunks) and close
other applications. The launcher's **Low-memory device** tick only affects building from
source, so it does nothing here.

## Limits

- Online-mode servers refuse this build by design; LAN and offline worlds work.
- Skins and capes need a Microsoft session and are not fetched.
- This release is built for Minecraft **26.3** and the same source commit as its tag. When the
  fork moves to another Minecraft version, a new release is needed.
- The game is in development; worlds are compatible with the source build of the same version,
  but back up anything you care about.

## If something goes wrong

- "Java not found" — install Java 25; the launcher names the path it looked for.
- "Minecraft 26.3 not found" — point **Browse…** at the folder your launcher installed it into.
- The window does not open — `./tools/launcher.sh --self-test` prints what it found; the usual
  cause is a Python without tkinter.
- The game is silent — preparation copies the sounds from your Minecraft install; tick **Copy
  the sounds** and press **Prepare game files**.
- A crash or an odd render — the game writes `logs/latest.log` under the **Worlds & settings**
  folder, and the launcher keeps its own log there too.

Full instructions and troubleshooting: `README.md` and `docs/` in the repository.
