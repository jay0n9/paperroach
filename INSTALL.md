# Installing PaperRoach

This guide takes a new user from an empty machine to one generated Obsidian
paper note. It covers Windows, macOS, and Linux. The currently verified
installation path uses uv to install the published PaperRoach command in its
own isolated environment.

## What you will install

PaperRoach connects four local tools:

| Component | Required? | Purpose |
|---|---:|---|
| Python 3.11 or 3.12 | Yes | Runs PaperRoach |
| Obsidian | Yes | Stores generated Markdown notes |
| Ollama | Yes | Runs the local text and embedding models |
| Zotero | Optional | Supplies bibliographic metadata and watched PDFs |

The default Ollama models require several gigabytes of download and storage.
A GPU is helpful but not required by PaperRoach itself; CPU inference is much
slower. PaperRoach swaps the text and embedding models instead of keeping both
resident at the same time.

## 1. Install the companion applications

### Obsidian

1. Install Obsidian from the
   [official download page](https://obsidian.md/download).
2. Create a new vault or open the vault that will hold your research notes.
3. Keep its path available. PaperRoach detects vaults that Obsidian has opened
   at least once.

PaperRoach requires an existing Obsidian vault. The safe setup command will not
turn a mistyped path into a new folder.

### Zotero

Zotero is optional for building a PDF manually, but recommended for automatic
metadata and attachment watching.

1. Install Zotero from the
   [official download page](https://www.zotero.org/downloads).
2. Open Zotero once.
3. Add or download at least one PDF attachment if you want to test the watcher.

PaperRoach opens `zotero.sqlite` read-only. It does not edit the Zotero library.

### Ollama

PaperRoach downloads models through Ollama but does not install or start the
Ollama application itself.

#### Windows

Install Ollama using the official Windows installer:

- [Ollama for Windows](https://ollama.com/download/windows)
- [Windows documentation](https://docs.ollama.com/windows)

After installation, Ollama normally runs in the background and exposes the
local API at `http://localhost:11434`. Open a new PowerShell window and verify:

```powershell
ollama --version
ollama list
```

#### macOS

Download the DMG, move Ollama into Applications, and launch it once:

- [Ollama for macOS](https://ollama.com/download/mac)
- [macOS documentation](https://docs.ollama.com/macos)

Then open a new terminal and verify:

```bash
ollama --version
ollama list
```

#### Linux

Follow the [official Linux instructions](https://docs.ollama.com/linux). The
standard installer is:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Start the service supplied by your installation, or run this in a separate
terminal:

```bash
ollama serve
```

Then verify:

```bash
ollama --version
ollama list
```

## 2. Install uv

PaperRoach currently supports Python 3.11 and 3.12. Python 3.13 and newer are
not yet in the supported package range. Python 3.12 is recommended for a new
installation.

Install [uv from its official instructions](https://docs.astral.sh/uv/getting-started/installation/).
PaperRoach uses uv to install the newest available Python 3.12 patch into a
managed location, so this guide does not pin you to an old Python installer.
You do not need to install Python separately.

- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
- [uv-managed Python](https://docs.astral.sh/uv/guides/install-python/)

## 3. Install PaperRoach

uv gives PaperRoach its own environment and exposes the `paperroach` command
without requiring you to clone the repository, activate a virtual environment,
or manage dependencies manually:

```bash
uv --version
uv python install 3.12
uv tool install --python 3.12 paperroach
paperroach --version
```

Expected final line:

```text
paperroach 0.1.0
```

If uv warns that its tool executable directory is not on `PATH`, run
`uv tool update-shell`, close the terminal, and open a new one before checking
the version again.

## 4. Run safe first-time setup

```bash
paperroach setup --pull-models
```

Setup performs the following actions:

1. Discovers existing Obsidian vaults.
2. Selects the only vault automatically, or asks when several are found.
3. Writes a small user-wide config.
4. Creates `References/` and `.kb/` inside the selected vault.
5. Detects Zotero when possible.
6. Downloads the configured Ollama models.

For a new config, the downloaded models are:

| Model | Role | Installed when |
|---|---|---|
| `qwen3:8b` | Paper analysis and note generation | Always |
| `bge-m3` | Embeddings and semantic search | Always |
| `qwen2.5vl:7b` | Figure descriptions | Only when `figure_mode = "describe"` |

Model pulls are resumable by rerunning the same setup command. Existing custom
model tags in the config are honored.

If no vault is detected, choose one explicitly:

```bash
paperroach setup --vault "path/to/your/ObsidianVault" --pull-models
```

The path must already contain an `.obsidian` directory. Open it in Obsidian
first if setup reports that it is not a vault.

If several vaults are found, setup displays a numbered choice:

```text
Obsidian vaults:
  1. C:\Users\you\Documents\ResearchVault
  2. D:\Notes\PersonalVault
Choose a vault [1]:
```

Setup is safe to rerun. A config for the same vault is kept unchanged. A config
for another vault is not replaced unless you review it and pass `--force`.
Because `--force` writes a new minimal config, back up any custom options in
the previous file first.

The advanced `--config PATH` option writes somewhere other than the default
user location. Later commands will find that file only when `KB_CONFIG` points
to the same path.

## 5. Verify the installation

Run:

```bash
paperroach doctor
```

A new library normally reports zero failures and may warn that the LanceDB
store has no tables yet. That store warning disappears after the first
successful build.

The important checks are:

```text
[OK] Vault
[OK] Zotero
[OK] Ollama
[OK] Text model
[OK] Embed model
```

Zotero may be a warning if it is not installed; manual PDF builds still work.
A missing model is a failure, and `doctor` prints the exact `ollama pull`
command needed to fix it.

For an offline configuration-only check:

```bash
paperroach doctor --skip-ollama
```

## 6. Build the first paper

Start with one PDF instead of scanning an entire Zotero library:

```bash
paperroach build "path/to/one-paper.pdf"
```

Always quote paths that contain spaces. The generated paper note appears under:

```text
<vault>/References/<Domain>/<Subdomain>/
```

Concept notes are written under `<vault>/6 - Knowledge Library/`, and the local
search index is stored under `<vault>/.kb/`.

Try retrieval after the build:

```bash
paperroach search "the paper's main method"
paperroach ask "What is the paper's main contribution?"
```

## 7. Enable Zotero automation

First confirm that `paperroach doctor` reports a Zotero directory. Detection
uses this order:

1. Explicit `zotero_dir` in the config.
2. A custom `dataDir` found in the Windows Zotero profile.
3. The default `~/Zotero` directory.

The default path works across supported operating systems. A custom macOS or
Linux data directory may need to be added manually to the user config:

```toml
zotero_dir = "/path/to/Zotero"
```

Process existing unindexed attachments once:

```bash
paperroach watch --scan
```

The scan exits when it finishes. Start continuous watching separately:

```bash
paperroach watch
```

Stop the continuous watcher with `Ctrl+C`. PaperRoach reads Zotero attachment
PDFs and bibliographic metadata but does not write to the Zotero database.

## 8. Optional PDF and figure features

Reinstall the tool with the desired package extra. This keeps the same
`paperroach` command and isolated environment.

### Scanned PDFs

```bash
uv tool install --python 3.12 "paperroach[ocr]"
paperroach build "scanned-paper.pdf" --ingester ocr
```

### Layout-aware figure extraction

```bash
uv tool install --python 3.12 "paperroach[docling]"
```

To keep both optional feature sets, install
`paperroach[ocr,docling]` in the same command.

Add the following to the effective `kb.toml`:

```toml
figure_mode = "describe"
figure_backend = "docling"
vision_model = "qwen2.5vl:7b"
```

Then download the additional configured model and verify:

```bash
paperroach setup --pull-models
paperroach doctor
```

Nougat is an advanced math-aware backend with heavier GPU and dependency
requirements. It is not part of the recommended first installation.

## 9. Configuration locations

The default setup config is:

| Operating system | Path |
|---|---|
| Windows | `%APPDATA%\PaperRoach\kb.toml` |
| macOS | `~/Library/Application Support/PaperRoach/kb.toml` |
| Linux | `$XDG_CONFIG_HOME/paperroach/kb.toml` or `~/.config/paperroach/kb.toml` |

Configuration values use this precedence:

```text
CLI flags > KB_* environment variables > selected config > built-in defaults
```

Config files are selected in this order:

```text
KB_CONFIG > <explicit vault>/kb.toml > ./kb.toml > user config
```

If setup warns about `KB_CONFIG`, `KB_VAULT`, or a local `./kb.toml`, resolve
that override before relying on the new user config.

## 10. Updating PaperRoach

```bash
uv tool upgrade paperroach
paperroach doctor
```

## Troubleshooting

### `paperroach` is not recognized

Add uv's tool directory to `PATH`, then open a new terminal:

```bash
uv tool update-shell
uv tool list
paperroach --version
```

### Python reports an unsupported version

Reinstall PaperRoach with a supported interpreter:

```bash
uv python install 3.12
uv tool install --python 3.12 paperroach
```

### Ollama is not found

Open a new terminal after installing Ollama and run `ollama --version`. On
Windows and macOS, also confirm that the Ollama desktop app is running. On
Linux, start the installed service or run `ollama serve`. Setup may already
have written the config and vault folders; rerunning `setup --pull-models`
after Ollama is available is safe.

### Ollama is reachable but a model is missing

Run:

```bash
paperroach setup --pull-models
paperroach doctor
```

An interrupted model pull can be retried safely.

### Obsidian vault is not detected

Open the vault in Obsidian once, then retry. Otherwise pass the existing vault
path explicitly with `--vault`. A plain folder without `.obsidian` is rejected
intentionally.

### Zotero is not detected

Open Zotero once and confirm `zotero.sqlite` exists in its data directory. Add
`zotero_dir` to the effective config when using a custom path that profile
detection does not find.

### A scanned PDF produces little text

Install the OCR extra and use `--ingester ocr` as shown above.

### Reporting an installation problem

Run `paperroach doctor` and include the following in the issue:

- Operating system
- Python version
- Ollama version
- PaperRoach version
- The redacted `doctor` output

Do not attach private PDFs, `zotero.sqlite`, personal notes, secret keys, or
unredacted home-directory paths.

## Privacy and removal

PaperRoach has no telemetry. Its runtime sends inference requests only to the
configured Ollama host. The default is localhost; a remote `ollama_host`
receives extracted paper text and any requested figure images.

Uninstall the isolated tool environment with:

```bash
uv tool uninstall paperroach
```

This does not delete generated Markdown, the user config, Ollama models, or the
vault's `.kb` index. Back up the vault and review those paths separately before
removing any retained research data.

## Success checklist

- `paperroach --version` prints a version.
- `ollama list` contains the configured text and embedding models.
- `paperroach doctor` reports no failures.
- One PDF creates a note under `References/`.
- `paperroach search` returns a result after the first build.
- Zotero is reported as `OK` before running `watch --scan` and then `watch`.
