# Lux In Music

Create songs from lyrics and a musical style, then listen to them in your browser.
Lux runs on your own computer. It is a prototype, with real audio tests on a Mac
with Apple Silicon, using YuE2 through audio.cpp.

You do not need to write code to install it. Follow the steps below in order.

## Take a look inside

Create music, find a direction with Vibe, remix stems and choose local models.
These example screens use synthetic songs and illustrations. Click an image to enlarge it.

| Create & Library | Vibe · images to musical style |
| --- | --- |
| [![Create and Library](docs/images/create.png)](docs/images/create.png) | [![Vibe image analysis and editable style](docs/images/vibe.png)](docs/images/vibe.png) |
| **Studio Mode · stem mixer** | **Settings · local models** |
| [![Studio Mode multitrack mixer](docs/images/studio.png)](docs/images/studio.png) | [![Settings and optional embedding model](docs/images/settings.png)](docs/images/settings.png) |

## Hear the Complete Demo

**Lux In Tenebris — Complete Demo** · Dance / Melodic Techno · **3:58**

A full song created locally with Lux, using YuE2 Q8_0 and the F16 VAE.
Press Play and enable sound to hear the original ending.

https://github.com/user-attachments/assets/51a82812-f433-4d41-804c-e34d2c7c23a7

[Install on a Mac](#install-on-a-mac) ·
[Open it again](#open-it-again-and-stop-it) · [Get help](#if-something-goes-wrong) ·
[Technical reference](#technical-reference)

## Install on a Mac

### Before you start

- A Mac with **Apple Silicon**: open the Apple menu → **About This Mac** and
  look for an Apple chip whose name starts with **M**.
- An internet connection for the first installation and model download.
- Free disk space for the app, a model and your songs. The default YuE2 model
  files take about **4.5 GB**, in addition to the software and generated audio.
  Model file size is not the total memory needed to run it.
- Access to [this GitHub repository](https://github.com/lvxworld/lux-in-music).
  If GitHub shows a missing page, sign in with an account that has access.

This guide covers macOS on Apple Silicon. Linux has a CPU setup path described
[in the technical reference](#other-platforms); a native Windows installer is
not provided.

### 1. Prepare your Mac — once

Open **Terminal**: press **Command + Space**, type **Terminal**, then press Return.

Copy this command into Terminal and press Return:

```bash
xcode-select --install
```

Follow Apple's installation window and wait for it to finish. These are the
Apple tools that Lux needs to prepare its audio engine. If Terminal says they
are already installed, continue to step 2.

### 2. Download Lux In Music

1. Open [the latest release](https://github.com/lvxworld/lux-in-music/releases/latest).
2. Under **Assets**, download `lux-in-music-v….zip`, which contains the complete
   app source for that version.
3. In Finder, open **Downloads** and double-click the ZIP to extract it, if it
   has not been extracted already.
4. Move the extracted project folder to a permanent location you can find again,
   such as **Documents**. It contains a file called **studio.sh**. Use this same
   folder for future launches.

For an earlier version, open [all releases](https://github.com/lvxworld/lux-in-music/releases)
and download its ZIP the same way. The green **Code** → **Download ZIP** button
gives the newest source instead, without a version number.

### 3. Start Lux and let it install the software

In Terminal, go into the folder you just extracted:

1. Type `cd`, then press the Space key.
2. Drag the extracted project folder from Finder onto the Terminal window.
3. Press Return. Terminal is now working inside that folder.

Copy this command into Terminal and press Return:

```bash
./studio.sh
```

On the first launch, Lux automatically prepares Python, its software dependencies
and the audio engine. **You do not need to install Python, uv, CMake or Homebrew
separately.** This step can take several minutes.

Terminal shows four stages:

| Stage | What happens |
| --- | --- |
| 1/4 | Check the required tools |
| 2/4 | Prepare Python and the app |
| 3/4 | Download and build the audio engine |
| 4/4 | Start Lux and open your browser |

Many lines of build output are normal. Wait until the app starts, and keep
Terminal open while you use Lux. If the browser does not open, visit
[http://127.0.0.1:8000](http://127.0.0.1:8000) after stage 4.

**This installs software only. Models are chosen separately in Settings.**

### 4. Choose your first music model

The first launch opens **Settings** because no model is active yet. A model is
what creates the music; its files must be downloaded before you can create songs.

1. Find the **YuE2-3B** card under **Models & Settings**.
2. For the first setup, leave **Main model precision: Q8_0** and
   **VAE precision: F16 (default)**. These are the combination used in the
   project's recorded Mac audio tests. Other choices use different amounts of
   storage and memory; the app tests a choice before activating it.
3. Open the license links and review the terms. If you accept them, tick
   **I have reviewed and accept these component license terms**.
4. Click **Download and activate**. If you already have the model files,
   the button can say **Verify and activate** instead.
5. Watch progress in that card. Wait for **Active · Verified**.

The download and short compatibility test can take a while. You can cancel and
retry a download. Optional separation models are for splitting a song into
vocals and instruments; you can leave them uninstalled for now.

Read [the model license notes](docs/model-licenses.md) before choosing a model
for commercial use. Licenses are shown before each download.

### Optional: suggest a style from an image

Open **Settings** and find **EmbeddingGemma 2**. Review its Apache-2.0 license
(Google's Gemma 4 license), then select **I have reviewed and accept these model
terms** and click **Download and prepare Vibe**. Lux downloads the pinned model
files to your computer (about 1.53 GB) and verifies them. This is separate from
YuE2 and does not change your music model. If Hugging Face asks for access,
accept its model terms on the linked model page and sign in from Terminal with
`hf auth login` before retrying.

Choose **Vibe** in the sidebar and add **1–5 JPG, PNG or WebP images**, up to
20 MB each. Remove or reorder them with the thumbnail controls, then click
**Analyze Images**. Lux compares them locally against **120 visual and musical
directions**, blending a shared atmosphere with complementary instrumental
textures. The catalog spans electronic, rock, metal, jazz, hip-hop, acoustic,
orchestral and regional musical traditions.

Edit the suggested style, then choose **Use in Create**. For compatible music
models, Vibe also suggests **Advanced settings** based on the variety between
your images. Review the values or uncheck the option to keep your own settings.
These creative presets use 8 rendering steps, which you can change in Advanced. Your lyrics,
title, seed and planning choices stay in the form. Image analysis works offline
after installation and does not start music generation.

The images become a **composite cover** and a local listening gallery for each
new song. You can remove them from Create before generating. During playback,
the gallery changes image every eight seconds with a slow dissolve. Use the
arrows or **Pause slideshow** to linger on an image. **Close image** or **Escape**
closes the view while the music continues; click the player cover to reopen it.
**Effects On / Off** controls a liquid glow and mirrored equalizer behind the
images. They react to the playing audio, with a softer glow during quiet passages.
Lux remembers your choice. Animation stops in pause and when the tab is hidden.
Reduced-motion preferences disable the effects and keep the slideshow manual.
Lux releases the embedding model when you leave Vibe.

### Build a song from your melody with Hook

Hook uses SheetSage2 to transcribe the leading melody from a local recording, including recordings with accompaniment. In Settings, review the licenses for SheetSage2 and its MERT component (both **CC BY-NC 4.0**) and explicitly choose **Download and prepare Hook**. The model files are about **2.76 GB**; Lux prepares an isolated Python 3.11 runtime. This does not change the selected music model. Analysis runs locally in FP32, uses Apple Metal when available and falls back to CPU. After installation, it works offline.

Open **Hook** and try the bundled example performance by Luke, played and recorded by Luke (not AI-generated), or record/upload one 2–90 second audio file (up to 25 MB). Listen to the extracted melody and check its tempo. Choose **Develop into a song** to guide the planned chorus, or **Arrange this recording** to use the melody-only score and its approximate length. Then select **Use in Create**, review your style, and start the normal generation flow. Hook never starts generation by itself.

The score is a musical guide; it does not preserve the original voice or instrument sound. Transcription and arrangement quality can vary, so listen to the preview before continuing. Recordings and temporary analysis files are removed after analysis and are not saved to the song library.

### 5. Create your first song

Lux infers song length during generation. The current release includes this
one-step flow: Lux analyzes the lyrics, style and tempo as part of generation.

1. Click **Create** in the sidebar.
2. Click **Demo · Melodic Techno** to load example lyrics and style. To try a
   different sound, open **Genre templates** and choose
   one of five styles. They use the same example lyrics.
3. Click **Create**. Lux analyzes the lyrics, style and tempo, chooses a song
   length, adapts the arrangement if needed, then generates the audio. This
   planning step uses model processing time. Progress shows each stage.
4. Your song appears in **Library**. Click it to listen, or use its download
   button to save the WAV audio file.

Loading a demo or template only fills in the form. Lux chooses the length from
the actual musical plan, rather than a duration value entered in advance. You
can edit the inputs for your own songs. Listen to each result to check its
phrasing and ending.

YuE2 checks that the full vocal arrangement fits its supported limit (currently
**5:30**), keeps vocal passages and the ending, and may shorten instrumental
sections. If the vocal material itself is too long to fit, Lux stops before
rendering and explains how to shorten it. Multiple variations share one analyzed
arrangement and differ in performance. The selected length is a plan estimate;
the sung performance may finish earlier, so listen to each result.

## Open it again and stop it

Keep the project folder: it holds the downloaded models, settings and songs.
You do not need to download another copy for each session.

On your Mac, double-click **Lux In Music.command** inside the project folder.
You can also open Terminal, enter that folder as in step 3, and run:

```bash
./studio.sh
```

Later launches reuse the installed software and models. Once a model is active,
Lux opens Create directly. Settings remembers your model and license review.

To stop Lux, return to its Terminal window and press **Control + C**.
Closing the browser tab leaves the app running in Terminal.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `Permission denied` when starting `studio.sh` | In the project folder, run the permission command below, then run `./studio.sh` again. |
| `No such file or directory` | Repeat step 3. Drag the folder that contains `studio.sh` into Terminal. |
| Apple Command Line Tools are required | Complete step 1, then start Lux again. |
| Setup stopped or a download failed | Read the error immediately above it. Fix that problem or restore your internet connection, then rerun `./studio.sh`. Retry a model download from Settings. |
| The browser did not open | Wait for stage 4, then open [http://127.0.0.1:8000](http://127.0.0.1:8000) yourself. |
| `Address already in use` | An app is using port 8000. Stop your previous Lux Terminal with Control + C, or use the alternate-port command below. |
| Create is disabled | Open Settings and finish activating a generation model. Its card must say **Active · Verified**. |
| A model needs verification or reports an error | Try **Verify and activate**. **Maintenance → Repair / recheck files** checks the files again. Keep the error text if you need help. |

If the downloaded scripts do not have permission to start, run:

```bash
chmod +x studio.sh scripts/setup.sh "Lux In Music.command"
```

To use another port, run:

```bash
./studio.sh --port 8001
```

The browser address is then [http://127.0.0.1:8001](http://127.0.0.1:8001).

The studio listens only on this Mac by default. To open it from another device,
choose an address you trust, such as your home network or Tailscale address:

```bash
./studio.sh --host 192.168.1.20
```

The studio has no login. Anyone who can reach that address can generate songs,
remove jobs, download your songs and start model downloads. `--host 0.0.0.0`
listens on every network, including public Wi-Fi. To use the studio from another
computer you control, an SSH tunnel keeps it private:
`ssh -L 8000:127.0.0.1:8000 your-mac`.

For help, open [an issue](https://github.com/lvxworld/lux-in-music/issues) and include
your Mac chip, memory, what step failed and the last relevant Terminal error lines.
Keep lyrics and style prompts private. Do not attach song metadata, request
files or logs containing them; describe the problem with the model, duration,
generation mode and error instead.
Your songs are saved in the **outputs** folder inside the project; keep that
folder when backing up your work.

## Model licenses

Model licenses are shown in Settings before any download. YuE2 weights and VAE
are published under **CC BY-NC 4.0**. Optional separation models have their own
terms; they are never installed automatically.
The upstream project also grants additional permission for individual creators
to monetize outputs. Company use of the weights has separate commercial terms;
see [the license review and official links](docs/model-licenses.md).

## Technical reference

### Security and private songs

Use the studio locally and keep private lyrics, styles and song files out of
GitHub reports. It has no login and must not be exposed to the internet.
See [the security policy](SECURITY.md) for supported use, private reporting and
maintainer publication checks.

### Contributing and project direction

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Any coding
CLI can use the shared instructions and run `python3 scripts/check.py`. See
[the harness guide](docs/harness.md) for application checks and CLI compatibility.

Maintainers can build a version from GitHub: open
[Actions → Release](https://github.com/lvxworld/lux-in-music/actions/workflows/release.yml),
click **Run workflow**, select **main**, and choose patch/minor/major. Leave
**Preview only** checked to run the tests and see the release plan. Uncheck it
on a second run to publish the version and downloadable files. No models are
downloaded. See [the release guide](CONTRIBUTING.md#release) for exact versions
and recovery instructions.

Local releases are built from `main` with `./release.sh patch` — or `minor`, `major`, an
explicit version such as `0.2.0`, and `--dry-run` to preview. The script checks
the repository, builds versioned artifacts from a temporary copy, then creates
a release tag and publishes the downloadable files. It leaves `main`, README
and `CHANGELOG.md` unchanged. Add `--full-checks` to also run the application
tests before publishing.

The [architecture contract](docs/architecture.md) explains provider/model adapters,
Settings, independent precision choices, and profile records. Track acceptance
scenarios in [harness/requirements.json](harness/requirements.json). Natural song
ending work (#1) now plans and checks EOS near the target before rendering, with
a real audio test and user listening acceptance. Clip mode can still cut off a song.

### Architecture

```
browser ──► studio (FastAPI :8000) ──► provider + model adapter ──► selected runtime
              │  Settings, queue, library                         lazy start
              └► outputs/<name>.wav | .json (profile + params) | model artifacts
```

* `vendor/audio.cpp/`: pinned inference engine, built for the catalog's local families
* `config/model-catalog.json`: pinned downloads, file sizes/checksums and component licenses
* `models/<model>/releases/<revision>/`: verified local artifacts; older downloads are reused
* `.lux/settings.json`: selected profiles, license reviews and verification records
* `.lux/runtime/`: generated runtime configs/logs; generation and separation use dynamic ports
* `studio/providers.py` + `studio/adapters/`: runtime lifecycle and model-specific behavior
* `studio/params.py` + `studio/engine.py`: shared inputs, WAV storage and profile metadata
* `studio/app.py` + `studio/static/index.html`: web studio
* `studio/cli.py`: generate one song from the terminal

### Advanced launch options

`./studio.sh` is the main launcher. `NO_OPEN=1 ./studio.sh` skips opening the
browser, and `./studio.sh --port 8001` changes the port. `scripts/setup.sh`
prepares software only; `scripts/run_studio.sh` starts an already prepared UI.
`scripts/run_engine.sh` serves the verified selected profile.

uv is installed locally if missing, Python 3.12 is prepared through uv, and
CMake 3.31.6 is supplied when needed. Source submodules use HTTPS, without a
GitHub SSH key. Startup downloads no model weights. The UI binds to
`127.0.0.1` unless `--host` is given, and Control + C stops it and its owned inference processes.

### Other platforms

Linux startup selects the CPU build. It requires Bash, curl, Git and a C/C++
compiler; for example, an Ubuntu/Debian installation can prepare them with:

```bash
sudo apt update
sudo apt install build-essential curl git
```

Then enter the project folder and run `./studio.sh`. The script prepares Python,
CMake if needed, and the CPU runtime. Real hardware/audio verification in this
project has been on Apple Silicon; Linux CPU performance and compatibility are
not claimed as tested. Native Windows startup is not implemented.

### Model setup details

1. Choose a generation model. YuE2 main choices are Q8_0, BF16 and Q4_0; choose
   the VAE separately (F16 by default, or F32). BF16 is different from FP16.
2. Review the component licenses and acknowledge the exact release. Unknown
   licenses block setup. Displayed file sizes exclude extra runtime memory.
3. Use the model's setup button to download missing files or verify existing ones.
   Progress appears in that card during transfer, checks and a short runtime test.
4. Open Create after activation. Only supported model controls are shown.

Verified profiles and license reviews persist across restarts. Returning to a
verified precision/VAE combination shows its saved status; switching to it uses
its existing validation. Changed files, releases or runtime binaries require
verification again. Active verified models show a disabled **Active · Verified**
button, including optional separators. **Maintenance → Repair / recheck files**
runs full checks when needed. Completed setup attempts do not accumulate above
the cards.

Downloads can be cancelled and retried; partial files resume when the server
supports ranges. Invalid files or a failed runtime test preserve the previous
selection. Existing downloads in the old model folder are verified and reused.
Optional separation models are installed and selected independently in Settings.
Saved songs remain playable without any active model. Editing needs their original
compatible generation/separation profiles. Changing Settings affects new jobs;
queued jobs retain their recorded selection.

The provider boundary also supports providers without local weights, precision
or a VAE. No MiniMax integration is included yet. For development, `LUX_STATE_DIR`,
`LUX_MODELS_DIR`, `STUDIO_OUTPUT_DIR`, `AUDIOCPP_BINARY` and `LUX_BACKEND` override
the corresponding local paths/runtime. Changing a runtime requires a new probe.

### Studio UI

* Create panel: title, lyrics with section-tag buttons, style with genre/mood/instrument/vocal/mix chips,
  implicit model-backed song-length analysis, planning progress, random/fixed
  seed, 1-4 variations, advanced sampling sliders, ABC input
* Genre templates: Progressive Metal, Indie Pop, Cinematic Synthwave, Soul & R&B,
  and Jazz Fusion. All use the Melodic Techno demo lyrics with the selected style,
  keeping your title and settings;
  applying a template starts no generation. The Melodic Techno demo remains above them.
* Library: generative cover art, waveform per song, live queue with progress/ETA, search
* Player bar: waveform scrubbing, prev/next, volume, download. Keys: Space play/pause, arrow keys seek 5 s
* Song panel: lyrics, all generation params, generated ABC score, reuse settings
* Untitled songs get an automatic title from the chorus hook

### Studio Mode: stem separation

Library row or song panel, then **Open in Studio Mode**: it asks what to separate, runs it on the engine,
then opens a multitrack mixer.

| Mode | Model (audio.cpp family) | Stems | License | Measured, 30 s song |
|---|---|---|---|---|
| Vocals & Instrumental | BS-RoFormer ep368 (`bs_roformer`) | vocals, instrumental | Publisher declares Apache-2.0; original checkpoint source undocumented | 33 s |
| 4 stems | HTDemucs (`htdemucs`) | vocals, drums, bass, other | MIT | 3.5 s |
| 6 stems | HTDemucs 6s (`htdemucs_6stems`) | + guitar, piano | MIT | 3.6 s |

Mixer: mute/solo/volume per stem, live meters, click-to-seek lanes, presets (Karaoke, A cappella,
No drums, Rhythm section), per-stem WAV download and **Export mix** (rendered in
the browser). Stems are stored in `outputs/stems/<song>/<mode>/` with a `stems.json`.

### Studio Mode: regenerate a piece of one stem

In the stem mixer press **Edit** on a track (only that track accepts a selection), drag across its lane,
then **Regenerate** (1-3 takes, lyrics optional). **Play selection** plays only that stem by default
(*Listen: Solo stem*) or the full mix. Only that stem changes inside the selection; every other stem stays
bit-identical. Each take is saved as a new tab of the stem set (`<mode>-take-<time>/`, with `base` and
`edit` in `stems.json`), so you can A/B the tabs and chain edits on a take.

How it works (`studio/separate.py` `replace_stem`, `studio/edit.py` `render_section`):
1. semantic tokens of the song (25/s): exported at generation time, or recovered by re-running the original
   request with `stop_after=semantic` (deterministic: re-render correlates 1.0000 with the original)
2. `semantic_prefix` = tokens before the selection, the model samples the selection with a new seed;
   tokens are spliced back (`new[:B] + old[B:]`) and the song is rendered once
3. the selection plus 3 s of context is separated with the same model as the stem set
4. only the chosen stem is crossfaded (0.2 s) into the selection

Measured: about 14 s per take with HTDemucs 6 stems. YuE2 writes the new part together with its own
backing, so a new vocal line usually fits the original band, but key or timing clashes are possible:
listen to each take.

### Look: after Lux In Tenebris

`studio/static/theme-lux.css` follows [luxintenebris.news](https://luxintenebris.news/): ink background, warm
newsprint text, amber lamplight as the only accent, ember used sparingly, thin rules and kickers. Covers are
generated as watercolour on aged parchment with a sepia-ink music staff (some "in tenebris", with a candle).
The sidebar uses the supplied gold Lux In Music logo, served locally. Its compact
layout shows the symbol from the same artwork. Interface text uses Inter.

CLI:

```bash
uv run studio-gen --help
```

The CLI help explains how to provide your own local input file and musical style.
It uses the same automatic length analysis as the browser.

## Parameters (v0.1)

The API accepts common song fields plus a `model_options` object validated by
the selected adapter. Legacy flat YuE2 options still work. The table below applies
to the YuE2 adapter; these options are not required by other providers.

| UI / API field | YuE2 option | Default | Notes |
|---|---|---|---|
| lyrics | `lyrics` | empty; optional | Section tags describe the song structure; Instrumental ignores this text |
| style | `style` | (required) | language, genre, instruments, vocal, mix |
| cot | `cot` | full for automatic complete-song generation | YuE2 plans an ABC score to infer length and protect the ending |
| seed | `seed` | 1234 | same params + seed gives the same song |
| num_inference_steps | `num_inference_steps` | 8 | NAR ODE steps |
| guidance_scale | `guidance_scale` | 1.01 (off) / 1.0 | |
| temperature / top-p / top-k / rep. penalty | `semantic_*` | 1.0 / 0.95 / 100 / 1.2 | |
| abc | `abc` | (none) | condition on your own ABC score (needs cot=melody/full) |

The browser, API and CLI infer the arrangement length as part of one generation
job. Users cannot supply a target or a hard duration cap. The generated song
records Lux's selected plan length and any ending/truncation evidence. See
[duration and ending behavior](docs/song-endings.md) for model limits, retries
and listening guidance.

## Measured on M4 Max (Q8 + F16 VAE, Metal)

| Run | Audio | Wall time |
|---|---|---|
| cot=off, cold start (includes model load) | 30 s | 40 s |
| cot=full, warm | 30 s | 15 s |
| cot=off, warm, 60 s cap (model ended the song on its own) | 37.8 s | 16.5 s |

## Roadmap ideas (next steps)

1. Extend / continue a song (`semantic_prefix` + `export_semantic`)
2. Style change mid-song (splice semantic tokens, see `vendor/audio.cpp/examples/yue2_style_change`)
3. Cover / remix from an ABC melody (`cot=melody` + `abc`), and score editing in the UI
4. Batch variations (N seeds per prompt), likes, and persistent projects
5. LoRA styles (`yue2.ar_lora`, `yue2.nar_lora`)
6. Studio features: stems (source separation), waveform timeline, trim/fade, MP3 export
