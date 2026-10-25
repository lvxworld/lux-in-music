# Project handoff

## Blue sidebar logo

- Replaced the gold PNG with the supplied blue artwork on a black background,
  preserving the source file unchanged. This replaces the earlier starry blue
  version. Updated the CSS framing for its layout and the favicon colors.
- Reduced the displayed logo by 10%, centered it, and rounded its corners to
  8 px. The compact sidebar shows the symbol at 36 px wide.
- Verification: baseline and full offline checks passed (183 tests). A focused
  Chrome check passed desktop, compact and mobile layouts, exact source-image
  delivery, no page overflow and no JavaScript errors. Desktop and compact
  screenshots were inspected under ignored `outputs/checks/blue-brand/`.
- The full browser flow was not rerun. Next step: review the new logo in the
  running app. Work continues on `feat/lux-hook`, including the Advanced help,
  layout improvements and brand changes from `feat/advanced-parameter-help`
  and `feat/brand-wordmark`.

## Sidebar brand refresh

- Added the supplied gold Lux In Music PNG as the sidebar logo. The source
  image is copied unchanged; CSS viewports hide its black margins and show only
  its symbol in the compact sidebar. It loads locally without remote requests.
- A simplified SVG symbol is used for the browser favicon. The earlier font
  proposal was replaced by the lettering in the supplied artwork.
- Removed the Latin sidebar tagline. Moved NEW from Vibe to Hook in both
  navigation menus, including a CSS fix so the mobile badge stays visible.
- Verification: full offline checks passed (183 tests). A focused Chrome smoke
  test passed exact source-image reuse with remote requests blocked, desktop and
  compact brand layouts, mobile Hook badge visibility, and no page overflow or
  JavaScript errors. Screenshots were inspected. The full browser flow was not
  rerun; its previously recorded Advanced tooltip failure remains open.
- Next step: check the published feature branch and its CI results on GitHub.

## Resizable Create and Library panels

- Create now opens wider by default, while protecting a readable minimum
  Library width of 360 px on wide layouts and 320 px on compact desktop layouts.
  The separator is draggable, keyboard adjustable,
  and remembers its width locally. It is hidden on mobile and non-Create pages.
- The divider's dynamic maximum now caps Create at 48% of the available pane
  width, preserving at least 52% for Library. Assistive technology also reports
  both pane widths while resizing.
- Added a 🎲 button beside the Style of music label, matching the seed control.
  It composes a random style from the existing genre, mood, instrument, vocal
  and mix options, then updates the matching chips for further editing.
- Song detail actions group WAV, FLAC, MP3 and an available score under Export;
  playback, Studio Mode, reuse and delete are arranged as separate actions.
- Hook reference audio in song details now loads metadata immediately so the
  native player has its full timeline and controls on first render. Older Hook
  songs without a saved source recording say explicitly why playback is missing.
- Vibe image and Hook audio reference cards now appear directly below the song
  title in Create, keeping source assets beside the song identity.
- Added browser-flow coverage for pointer resizing, keyboard adjustment,
  persisted width, and export grouping, plus static UI regression checks.
- Verification: `.venv/bin/python scripts/check.py --full` passes (183 offline
  tests). Browser-flow execution could not start: Playwright is absent from the
  system Python environment, and the offline `uv` attempt could not access its
  cache under the filesystem sandbox.

## YuE2 Advanced parameter help

- Added concise English explanations to all six Advanced sliders and the
  optional ABC score field. Help opens on hover and keyboard focus, following
  the explanations and defaults in the official audio.cpp YuE2 reference.
- Added browser-flow assertions for tooltip presence and both interaction modes,
  plus an API/static regression check for the help content.
- The descriptions explain sampling and rendering tradeoffs without promising
  audio-quality gains from increasing a setting.
- Left-column tooltips now open from the icon toward the Create panel instead
  of extending underneath the sidebar; right-column tooltips open inward too.
- Hook now explains that its melody-reference workflow currently creates
  instrumental songs only because it cannot yet combine the reference with
  sung lyrics. The misleading suggestion to use lyrics in Arrange was removed.
- Verification: the latest `.venv/bin/python scripts/check.py --full` passes
  (183 offline tests, including the baseline). Browser-flow execution could not
  start: Playwright is absent from the system Python environment, and the offline
  `uv` attempt could not access its cache under the filesystem sandbox.

## Studio Mode edit direction

- Added an optional “Direction for this part” field to the selected-section
  Regenerate controls. It is passed independently of lyrics, limited to 500
  characters, and saved in the generated stem take's metadata for later review.
- YuE2 receives the direction as an addition to its style prompt while sampling
  the selected semantic section. The existing time-range splice and chosen-stem
  replacement stay in place. YuE2 has no native section-only instruction field,
  so the direction guides the result but cannot guarantee exact compliance.
- Verification: `python3 scripts/check.py` and `.venv/bin/python
  scripts/check.py --full` pass; the latter runs 176 offline tests including
  mocked YuE2 conditioning and API length validation. The browser flow could
  not start because Playwright was not installed in the environment and the
  restricted network could not reach PyPI. Real YuE2 behavior still needs the
  user's Studio Mode listening test.

## SheetSage2 replaces the Hook pitch detector

Branch: `feat/lux-hook`, local only. The user approved the melody-only YuE2 arrangement and asked to use SheetSage2 as the only Hook model.

- Hook now uses SheetSage2 as its only transcription model. The UI supports the full recording path and offers Develop or Arrange; Arrange carries the official melody-only ABC score into YuE2.
- Settings presents SheetSage2 and MERT source, pinned revisions and CC BY-NC 4.0 terms. Download and runtime preparation remain explicit. Files are hash-verified and saved under ignored model/runtime folders; subsequent analysis is offline.
- Analysis runs in an isolated short-lived Python process using FP32, Metal when available and CPU fallback. Temporary recording and derived files are removed after each request. The model is not loaded at Lux startup and does not alter the active music profile.
- The prior local listening trial completed on Apple Metal. Melody-only conditioning produced a complete 71.84-second instrumental YuE2 result under an explicit 90-second target; the user accepted that result as musically strong. This is one listening result, not a general quality guarantee.
- The browser fixture now supplies synthetic SheetSage2 output. Verification has not been run after this integration change, and automated tests for the production manager remain to be added. Do not push yet.

## Hook instrumental reference: finishing limit and transcription review

- A real 71.65-second stereo reference was analyzed in Arrange recording mode.
  The saved score lasted 73.04 seconds at the estimated 138 BPM. Both original
  semantic attempts hit the 90-second hard limit with no EOS. The message about
  shortening verses or choosing a longer duration was inappropriate for this
  instrumental, automatically timed workflow.
- Controlled local inference kept the original request and changed only its
  token budget: the same seed emitted EOS at 91.96 seconds. A separate variant
  with conventional ABC spelling and an instrumental description also emitted
  EOS, but the budget-only trial isolates the finishing-limit cause.
- Arrange recording now gets a bounded finishing allowance: target plus the
  larger of 30 seconds or 25%, within the existing 360-second ceiling. Only the
  late-ending tolerance changes; early/dropped-section checks remain strict.
  No truncated stream is rendered. Normal plans and Develop mode are unchanged.
  Failure advice is specific to recording phrases and detected tempo, and the
  result records/displays the reference-to-performance timing difference.
- A full real generation through the shared engine and existing native endpoint
  completed with Q8_0/F16 at 92.16 seconds and observed EOS. The WAV and report are
  under ignored `outputs/checks/hook-ending-review/`. This verifies the ending
  path, not musical fidelity; the user's listening acceptance is still pending.
- Additional local feasibility checks used the already installed EmbeddingGemma
  audio encoder, with vision disabled and local-only loading. Three eight-second
  segments ranked an instrumental acoustic-guitar description highest among
  candidate descriptions. This is semantic association, not verified instrument
  identification. No captioning model or remote inference was used.
- A separate local HTDemucs 6-stem pass on a 20-second excerpt produced
  substantial bass, guitar and drum stems and very low vocal/piano energy.
  This supports reviewing an instrumental/polyphonic path; separator labels
  and stem levels are not instrument-identification confidence or a listening
  acceptance. Diagnostic audio remains under ignored outputs.
- Spotify Basic Pitch's public Apache-2.0 previous runtime model (230 KB, revision
  `fa5997af0a8210982619003269994a1be25eddf3`) and reference decoder were evaluated
  in a temporary directory. It found overlapping note events throughout most of
  the recording. A local synthesized polyphonic preview was saved for review.
  This confirms a polyphonic transcription route can run locally, not that a
  correct melody/chord decomposition has been accepted. Basic Pitch and audio
  instrument/style analysis are not integrated into Hook or its Settings yet.
- Offline regressions cover the extra release margin, unchanged native timing,
  refusal to render capped or overly early reference results, and the advisory
  transcription warning. Full offline checks passed with 186 tests; the focused
  Hook Chrome flow also passed after the advisory changes. Next: listen to the full instrumental trial and the
  note preview, then decide how to expose polyphonic instrument references.

## LUX HOOK local implementation

Branch: `feat/lux-hook`, local changes only. The page records or uploads one local audio file, supports device selection and range trimming, previews the selected melody, and transfers the reviewed reference into Create while preserving other form fields. SheetSage2 is now the only Hook transcription model; the prior pitch-model implementation and local weights have been removed.

- Setup and licenses are managed in the Hook Settings card, independently of music generation profiles.
- Develop mode fits melody notes into the planned arrangement. Arrange mode transfers SheetSage2's melody-only score with approximate recording timing. The YuE2 adapter retains its normal duration and ending checks.
- A local real-model test on Apple Metal and two YuE2 trials were completed before integration. The user accepted the melody-only arrangement. Automated and browser checks have not been run after the current model replacement.
- Next: review the fake inference fixture and run the baseline, full offline suite, browser flow, then listen to an arrangement from the Hook page. Keep the branch local until verification and listening acceptance are complete.

## Stronger glow in the Vibe listening effects

Branch: `feat/lux-vibe-v0-1`.

- Follow-up on the author's note: the background behind the artwork was not
  glowy or engaging enough. The visualization now centers on a hot halo that
  blooms directly behind the artwork (aura, bloom, core and a white-hot
  point), with slow concert light shafts that rotate around it.
- Bass onsets above their recent floor kick the halo with a decaying pulse.
  Ambient pools slowly trade palette colors; liquid ribbons gained a wide
  haze pass around their bright core; mirrored spectrum pillars carry a soft
  aura; warm embers rise and twinkle with the treble.
- The artwork itself now breathes: an energy- and bass-driven drop-shadow
  hugs the fitted image, gated on the same enabled state as the canvas. A
  depth vignette keeps the edges dark so the center reads as light.
- Same boundaries as before: one media element source, ≤ 960 × 720 raster at
  30 fps, drawing only while playing and visible, reduced-motion disables it,
  Effects On / Off persists. Sparkles are pre-rendered sprites; all glow is
  gradient-based, no shadowBlur.
- Verification: baseline and full offline checks pass (166 tests). The Chrome
  desktop/mobile flow passes, including live-audio/silence response, frozen
  frames on pause/hidden tabs, single media source, persistent toggle and the
  unavailable-context playback case. Screenshots remain ignored files under
  `outputs/checks/ui/`.
- Fixed along the way: the Vibe settings card assumed every status payload
  carries a revision and threw `undefined.slice` on each poll when it did not
  (the browser flow's minimal mocked status triggered it). The source and
  revision paragraph now renders only when the payload includes it.
- Next step: visual acceptance with a full-length song on the target Mac.

## Vibe runtime update replaced the running environment

- Observed: installing EmbeddingGemma 2 from Settings failed with "the installed
  version is missing", although `.venv` then contained Sentence Transformers
  6.1.0. The running server used Python 3.12; the new `.venv` used Python 3.13.
- Cause: setup syncs with `--python 3.12 --inexact`, but the Settings runtime
  update ran plain `uv sync --frozen --extra vibe`. uv chose another Python and
  recreated `.venv` while Lux was running, so its 3.12 site-packages vanished
  and every Vibe module looked missing.
- Fix: the runtime update now passes `--inexact` and `--python sys.executable`,
  so it adds the Vibe extra to the existing environment. A fake-uv regression
  test checks the command. Full offline checks pass.
- Next step: rerun `./studio.sh` (it rebuilds the 3.12 environment), then retry
  the install from Settings with the real runtime.
- After the runtime update and restart, a `.jpeg` upload was rejected as "Use a
  JPG, PNG, or WebP image". Phone and camera JPEGs that carry extra pictures
  are reported by Pillow as MPO, not JPEG. Vibe now accepts MPO and analyzes the
  primary picture. A real synthetic two-picture MPO is accepted and decoded to
  its first picture; a fake-Pillow regression test covers the format check.
- Vibe analysis and install failures now log their traceback (and uv's error
  output) to the Lux terminal; the browser still gets the short message.
- Lux restarts itself after a Vibe runtime update. It waits until no generation,
  separation, stem edit or model download is queued or running, shuts down
  cleanly, and re-executes the same interpreter with `--no-open`, so the
  terminal, PID and Ctrl+C stay the same and the open tab reconnects. Hosts
  that do not use `studio.launch` keep the manual restart message. Verified with
  unit tests and a real launcher on a spare port (same PID, back in about 1 s).
  Queued jobs are in memory, which is why restarts wait for an idle queue.
- Vibe rejected phone photos above 20 MP. That cap was Lux's own; Pillow's
  decompression-bomb limit is about 89.5 MP and EmbeddingGemma 2 sees at most
  about 0.65 MP (280 tokens of 48 × 48 px). Vibe now accepts up to Pillow's
  limit, decodes JPEGs at reduced scale and downscales to 2048 px before
  analysis. A real synthetic 8064 × 6048 JPEG decodes to 2048 × 1536 in 0.08 s
  and is analyzed by the installed model. The per-image file limit is now
  20 MB (was 10 MB) in the server, browser check and README, so full-size phone
  JPEGs fit; a five-image request may now be up to about 100 MB.

## Clean-environment CI dependency fix

- Both push and pull-request jobs exposed a missing base dependency:
  `vibe_runtime_status()` uses `packaging.version.Version`, but packaging was
  only available through the optional embedding runtime on the development Mac.
- Declare packaging directly in the application dependencies and refresh the
  lock. Keep all embedding libraries and model downloads optional.
- Verification: the full offline harness passes all 155 tests in a newly
  created base-only environment. Confirmed that Torch, Sentence Transformers
  and Pillow are absent, matching the optional-runtime boundary in Actions.

## Audio-reactive glow in the Vibe listening gallery

Branch: `feat/lux-vibe-v0-1`.

- Added softly moving amber, rose and teal light pools, liquid ribbons and
  mirrored frequency bars behind the inspiration images. Real playback RMS and
  bass/mid/treble bands drive the effect with smoothed attack and release.
- Effects On / Off remembers its state. Drawing stops on pause, image-view
  closure and hidden tabs; reduced-motion preferences disable it. A single
  Web Audio media source keeps playback continuous across repeated toggles.
- The renderer uses at most 960 × 720 pixels at 30 fps. This bounds rendering
  work; no device-wide performance benchmark is claimed.
- Chrome checks use a synthetic bass/mid tone and silence to verify amplitude
  response, frozen frames during pause/hidden tabs, one media source, persistent
  toggling and mobile controls. A failed-context scenario checks that ordinary
  playback still works. Existing gallery and application regressions remain.
- Full offline harness passes 155 tests. Chrome desktop/mobile checks pass,
  including the unavailable-context playback case, without JavaScript errors.
  Browser verification and visual review
  use isolated data; effect screenshots are ignored files under
  `outputs/checks/ui/vibe-effects-desktop.png` and `vibe-effects-mobile.png`.
- Next step: visual acceptance with a full-length song on the target Mac.

## Shared starter lyrics for Create and Vibe

- Updated the initial Create lyrics, including a short closing Outro.
- Use in Create from Vibe fills an empty or whitespace-only lyrics field from
  that same default and dispatches input/change events. Existing writing remains
  intact, as do the selected title, seed, planning and instrumental mode.
- Browser coverage checks the shared default and line counter on empty-field
  transfer, alongside the existing check that custom lyrics survive transfer.
- Verification: all 155 offline tests and the Chrome desktop/mobile flow pass.

## Vibe interface polish and lighter generation presets

Branch: `feat/lux-vibe-v0-1`.

- Direct, Melody and Full score have outlined icons and simple English helpers
  on hover and keyboard focus. A note explains that complete-song fitting can
  select a full score automatically.
- EmbeddingGemma shares the responsive model-card grid. NEW appears on Vibe in
  desktop and mobile navigation, rather than Studio Mode.
- Removed SAM Audio from the downloadable catalog and new separation choices.
  Legacy stem-set labels and provider snapshots remain supported. On the local
  development machine, removed both hard links to its 3,095,951,072-byte weights
  and its Settings profile/review records, after backing up Settings under the
  ignored `.lux/backups/` directory. Existing songs and stems were not removed.
- Every image-guided YuE2 preset suggests exactly 8 rendering steps; image
  diversity still changes temperature, top-p and top-k. Advanced remains editable.
  The preset test verifies both normalized values and native request options.
- Vibe's waiting message explains model loading and the first catalog build.
  PyTorch's macOS log-redirection warning does not itself stop inference; it is
  unrelated to the rendering step count. No timing benchmark is inferred from it.
- README now shows Create/Library, Vibe, Studio Mode and Settings above the audio
  demo. Captures use the real interface with isolated synthetic showcase data,
  original geometric illustrations and silent mixer audio. Regenerate with
  `uv run --no-project --with playwright python scripts/check_ui.py --readme-screenshots`.
  Screenshots were visually inspected after capture.
- Screenshot verification found that programmatic Studio navigation from Vibe
  left the previous view class active. Studio now synchronizes the existing
  Settings and Vibe routes after pushState; browser checks assert that the mixer
  is visible and only one sidebar link is selected.
- Verification: full offline harness passes 155 tests. Chrome desktop/mobile
  flow passes without JavaScript errors, including card width, hover/keyboard
  helpers, retired-mode removal, 8-step transfer and cross-page routing.
- Next step: compare the 8-step music rendering by listening before making any
  quality or speed claims. This pass verifies preset delivery, not a new audio
  benchmark or a comparative listening result.

## Five-image Vibe palettes and broader catalog

Branch: `feat/lux-vibe-v0-1`.

- Vibe accepts 1–5 images with add, replace, remove and ordering controls.
  Every image is limited to 10 MiB and 20 megapixels; multipart uploads reject
  a sixth image. Decode and inference run sequentially in the worker thread.
- Expanded the curated catalog from 40 to 120 stable visual/music entries,
  covering more electronic, acoustic, metal, jazz, hip-hop, orchestral and
  regional traditions. Catalog content automatically invalidates text caches.
  Normalized image vectors select individual matches and a shared centroid
  direction; complementary catalog textures enrich the combined style.
- YuE2 owns three conservative image-guided sampling presets. The Vibe result
  shows the values and an opt-out. Use in Create applies only supported controls
  and checks that the music profile has not changed. Lyrics, seed, title and
  planning remain the user's inputs. The mapping is a creative heuristic,
  rather than an upstream claim that images determine ideal sampling values.
- Each new song gets a mosaic cover and independent gallery JPEGs, stripped of
  image metadata. The player crossfades images every eight seconds, supports
  arrows and slideshow pause, and stops auto-advance when playback pauses or the
  tab is hidden. Reduced-motion preferences keep it manual. Existing single
  image songs and their covers still work.
- Verification: full offline harness passes 154 tests, including 35 Vibe tests.
  Chrome checks cover five-file limits, removal/reordering, Advanced opt-out
  and transfer, all five colors in the actual JPEG collage, persistence,
  automatic carousel timing, pause, manual controls and mobile layout.
- Real offline EmbeddingGemma analysis accepted five synthetic PNGs against
  all 120 entries and returned a blended style and a Balanced blend preset.
  A native YuE2 Q8_0/F16 rendering with the Contrasting textures preset produced
  a finite 7.999-second stereo WAV at 48 kHz (intentional 8-second smoke-test
  cap, peak 0.4715). The recording and report are local ignored artifacts at
  `outputs/checks/vibe/image-guided-sampling.wav` and its JSON sidecar.
- Limitation / next step: the presets need a comparative listening check before
  claiming a musical-quality improvement. The short native test verifies option
  acceptance and valid audio, rather than a complete arrangement or preference.

## Vibe song covers and listening view

Branch: `feat/lux-vibe-v0-1`.

- Use in Create now carries the analyzed image alongside the edited style. A
  preview in Create explains that it becomes the song's local cover and offers
  Remove. Loading another song, demo or genre template clears the draft image.
- Generation validates and resizes the image, strips embedded metadata and
  queues its prepared bytes in private job fields. Each completed variation
  receives its own JPEG artifact and Vibe catalog reference. Image data stays
  outside provider inputs and public jobs; cancelling a queued job releases it.
  Deleting one song removes its cover without changing another variation.
- Library, song details, Studio Mode and player use the saved image as the
  cover. Details identify the image inspiration. Playback opens a larger image
  with a soft fade above the player. Close image or Escape dismisses it while
  playback continues; pause/resume respects dismissal and the player cover
  reopens it. Reduced-motion settings remove the transition.
- Verification: full offline checks pass (147 tests). Chrome browser checks
  exercise Vibe transfer with existing form fields, real image persistence,
  cover reuse after reload, playback controls, closing/reopening and desktop
  and mobile layouts with synthetic inputs and fake inference. Settings and
  Studio Mode regression checks pass without JavaScript errors.
- Covers apply to newly created Vibe songs. Earlier image analyses did not
  retain their source image, so existing songs cannot recover it automatically.

## Current work: LUX VIBE image-to-style suggestions

Branch: `feat/lux-vibe-v0-1`.

- Fixed the repeated Vibe restart/update cycle: startup's exact base `uv sync`
  removed the optional runtime installed through Settings. Startup now preserves
  those packages with `--inexact`, without requesting extras on a fresh install.
  An offline bootstrap regression exercises two launches with a fake optional
  runtime and catches its removal. The Analyze API also handles `job: null`
  after a clean restart, instead of failing while reading the old update job.
- Real local inference uncovered a missing image dependency: the model processor
  needs torchvision. The optional Sentence Transformers dependency now includes
  its `image` extra, and runtime readiness checks image dependencies too. The
  existing model files were reused. A synthetic 64×64 PNG was embedded on CPU,
  matched to a real catalog entry, and the runtime released successfully.
  The same synthetic image passed through the real Analyze API with HTTP 200
  and a nonempty style, followed by successful API resource release.
  This smoke test also exposed a native crash when CPU cleanup called Metal's
  cache API; cleanup now touches Metal only for an available MPS device.
- Added a dedicated Vibe page and sidebar entry between Create and Studio Mode.
  It supports one JPG/PNG/WebP upload, preview/replace, local analysis state,
  editable catalog style, and transfer to Create without changing other form
  values. Desktop and mobile navigation share `#/vibe`.
- Added a separate optional model manager and Settings card for
  `google/embeddinggemma-2` at revision `c3f2237ce16fe33d1bb9dab8692c29c79865bdeb`.
  License acceptance precedes runtime preparation and model download. It stores
  model artifacts under ignored `models/vibe/`, verifies a SHA-256 manifest, and
  can reuse or repair local files. Neither `studio.sh` nor application startup
  downloads the model or Vibe runtime packages.
- The inference path loads Sentence Transformers lazily from local files, sets
  offline flags and `local_files_only`, omits the audio encoder, and uses FP32
  with MPS/CPU handling. It matches image embeddings against a local 40-entry
  visual-description catalog using normalized cosine similarity. No model
  repository code, image upload, embedding vector or score is exposed.
- Verification so far: `python3 scripts/check.py` passes; `.venv/bin/python
  scripts/check.py --full` passes with 147 tests, including 28 Vibe tests. The
  catalog/ranking, mocked runtime initialization, offline-only loading, API
  behavior, license gate, manifest verification, navigation and image checks
  pass without model weights or a GPU. `uv lock --check --offline` passes.
- The release wheel builds successfully and contains the Vibe catalog data.
- Fixed the Vibe download percentage: Hugging Face reports transfer bytes,
  reconstructed bytes, and file-count progress separately. Lux now reports only
  reconstructed model bytes and caps the displayed percentage at 100. The new
  bounded-progress regression test passes.
- The downloaded model metadata requires Sentence Transformers 6.1.0 or newer;
  the old Vibe extra installed 5.7.0, which caused local analysis to fail. The
  Vibe dependency and lock now require 6.1+, Settings can update the runtime
  while reusing the verified 1.53 GB model files, and analysis explains when a
  runtime update or app restart is needed. This environment now has Sentence
  Transformers 6.1.0. The Settings license acknowledgement is restored only
  when the saved license and review ID match the current model terms. The
  browser also clears a stale restart message after the new server confirms its
  status. Runtime version, license persistence and restart-state behavior have
  regression coverage.
- Full offline checks pass after these fixes (147 tests). The updated lock
  passes `uv lock --check --offline`; an offline dry run of startup's dependency
  sync reports no changes with the Vibe runtime installed.
- Chrome browser checks pass with fake embedding inference and synthetic
  images, covering Vibe, Settings, creation, Library and Studio Mode. Apple
  Silicon MPS acceleration has not been verified; real CPU inference passes.

## Release publication without changing main

Merged into `main`.

- The release workflow now derives the next version from the newest reachable
  release tag as well as `pyproject.toml`. This supports releases while `main`
  remains unchanged between versions.
- Release assets are built from a temporary copy of tracked `HEAD`; only that
  copy receives the release version in `pyproject.toml` and `uv.lock`. The source
  ZIP, wheel and sdist carry the selected version, while the checkout, README,
  CHANGELOG and `main` ref remain unchanged.
- Publication creates and pushes an annotated version tag on the current `main`
  commit, then uploads the assets and release notes. Branch protection can keep
  requiring pull requests. Tag rules may block updates and deletions while still
  allowing new release tags.
- Tests verify tag-based version selection, staged metadata, unchanged checkout
  version, release ZIP metadata and executable file permissions. `python3
  scripts/check.py` passes; `.venv/bin/python scripts/check.py --full` passes
  with 118 tests.
- A local release build of synthetic version `9.8.7` produced the source ZIP,
  wheel, sdist and checksums from the staging copy. The checkout still declares
  `0.3.1`; generated test artifacts were removed. Preview the GitHub workflow
  before the next real publication.
- The README no longer contains a manually maintained latest-release block.
  Its installation steps link to the latest release directly; release builds
  leave README and CHANGELOG unchanged.
- Next step: run the Release workflow preview from `main`, then publish when
  ready.

## Current work: infer song length inside generation

Branch: `feat/implicit-duration-generation`, issue #18.

- Replaced the separate duration analysis/review action with one Generate job.
  The shared engine analyzes lyrics/style/tempo, chooses an internal YuE2 target,
  fits instrumental sections while preserving vocals and the ending, then renders.
- Removed duration selection from the Create form, generation API and CLI. A job
  records Lux's inferred target and duration diagnostics in the song metadata.
  Variations share one checked score and use different performance seeds.
- The UI explains that model planning adds processing time and shows analysis as
  a generation stage. Plans beyond the model limit fail before rendering and
  suggest shortening verses or repeated sections. No private prompt text is used
  in fixtures, documentation or logs.
- The Planning controls remain visible for models that support them. Automatic
  length analysis no longer hides the section or changes the user's selected
  planning mode in the form.
- Offline tests cover single-job flow, API rejection of manual length fields,
  inferred target metadata, variation plan reuse and over-limit failure.
- Verification: baseline and full offline checks passed. A synthetic native run
  used YuE2 Q8_0/F16, seed 3217 and an explicit 100 BPM style. Lux inferred a
  60-second target from the 57.6-second score; the final WAV is 55.84 seconds,
  ended with EOS and was generated in 29.1 seconds. SHA-256:
  `b672f3a137b5488bcbfa0e6ea738b63245c4503dd105ecc26b991d6c07f99724`.
  The ignored local artifact is `outputs/implicit-length-smoke-20261011.wav`.
  Listening review is still pending; EOS and matching length do not establish
  musical quality.
- Browser automation could not run: Playwright is not installed in `.venv`, the
  configured uv cache is not accessible in this sandbox, and a temporary cache
  could not reach PyPI because DNS/network access is unavailable. A served-page
  regression test now checks that the manual control and separate endpoint are
  absent. This does not replace visual browser review.
- Limits: YuE2's complete arrangement target remains 30–330 seconds with a
  separate internal finishing cap up to 360 seconds. The estimate describes the
  score, not the final performed length. Native audio/listening check remains.

## Security review before public publication

- Reviewed current source, local refs, a fresh remote mirror, release packaging,
  model download integrity, dependency advisories and GitHub metadata. Detailed
  findings and private-history identifiers stay in a local maintainer report,
  outside Git. No confidential song content is added to this review.
- The fresh mirror contained 500 advertised Git objects, with no exact match for
  the known historical private inputs. All nine package archives across v0.1.0,
  v0.2.0 and v0.3.0 passed the same check and contained no runtime/model/song data;
  their available SHA-256 manifests matched. Archive secret-scan findings were
  copies of the documented WAV checksum described below.
- Checked 23 issue/PR bodies and three comments plus their retained edits, and
  90 accessible Actions logs against known private text. Current bodies/comments
  and logs passed this limited content check; retained-history findings require
  cleanup. No Actions artifacts were retained at the time of review. Details
  stay outside Git; this does not certify unknown sensitive text or attachments.
- Gitleaks 8.30.1 (official checksum verified) reports one finding in historical
  progress notes: a documented WAV SHA-256, not an authentication credential.
  The Python advisory audit reports no known vulnerabilities in the 22 installed
  dependency versions on the audited interpreter. This does not cover every
  Python/platform variant, native libraries or undisclosed vulnerabilities.
- Temporary synthetic API checks confirm that the studio accepts an arbitrary
  Host and allows unauthenticated library reads and deletion. Default loopback
  binding and absent CORS permission do not prove resistance to DNS rebinding.
  Shared/public hosting needs separate hardening; source publication is distinct.
- Added SECURITY.md, explicit environment/build-output ignores and weekly
  Dependabot updates for pinned Actions. Repository security settings still need
  maintainer review; ruleset reads were unavailable for this private account tier.
- The repository remains private. A local scanner cannot certify removal of
  retained sensitive GitHub objects or discussion edit history. Resolve those
  findings using the private maintainer report before changing visibility.

## Manual releases on GitHub Actions

Branch: `ci/manual-release-actions`, issue #22.

- Added a manually started Release workflow with a preview enabled by default,
  patch/minor/major selection and an optional exact version. It reuses release.sh
  and always runs full offline checks; no model setup or native runtime build.
- Preview/validation use a read-only token. Publication alone has contents write,
  uses the selected main revision, and refuses a stale main or existing tag.
  Releases are serialized. Official actions, including the existing check action,
  are pinned to verified upstream commit IDs. No personal token is configured.
- Seven portable regression cases cover preview/publication command selection,
  main/manual-event gates, exact versions, invalid values, injection-like input,
  downgrades, and refusing to start the script on invalid input.
- Baseline and full application checks passed locally (110 application test
  executions). PR #23 was merged after both GitHub check runs passed. The manual
  preview also passed on GitHub in run 38162985134. A preview does not build or
  upload packages; those steps run only during actual publication.
- README and CONTRIBUTING explain the GitHub buttons, permissions, stale-main
  handling and recovery files. Publication failures retain built files for seven
  days. Local release usage and model/song exclusion remain unchanged.

## Release v0.3.0

- The user requested a new version after merging PR #20. A minor release includes
  duration analysis/review, plan reuse, explicit-BPM fitting and the updated
  installation guide. README identifies v0.3.0 as the first release with this flow.
- Build and publication use `./release.sh minor --full-checks`, after its dry run,
  from synchronized main. The release creates source ZIP, wheel, sdist and checksums.
- GitHub CLI is downloaded temporarily from its official release with its archive
  checksum verified; authentication uses the existing GitHub access. No model or
  song files are included, and no private lyrics or prompts enter release notes.
- Published [v0.3.0](https://github.com/NTTLuke/lux-in-music/releases/tag/v0.3.0)
  from commit `7ee7164`. Baseline and full checks passed before and after the
  version bump. All four release assets are present; the three package digests
  match their local SHA-256 values. Archive checks found no runtime/model/song
  directories or known private-prompt markers. Main is synchronized with origin.

## Current work: review a duration estimate before creating audio

Branch: `feat/duration-analysis`, related to issue #18.

- Models declare duration-analysis support. YuE2 offers automatic duration and
  a manual target, with an explicit analysis/review step before audio generation.
  The Create panel explains model processing and first-use loading, shows queued
  and running states with indeterminate progress, and allows cancellation.
- The result shows the plan's nominal duration and BPM. A short target offers
  Use suggested duration, Edit lyrics and Edit style, with specific suggestions.
  Over-limit and supplied-score cases have their own messages. Changes to inputs
  or model invalidate the result; expired results ask for another analysis.
- Analysis runs only score planning in the existing queue. A bounded in-memory
  cache retains the plan for 30 minutes. Generation validates its inputs/profile
  and reuses it, including for performance variations. Queued jobs keep a copy.
- Added permanent repository guidance to keep private lyrics/prompts out of
  commits, issues, PRs, comments and tests. All new fixtures use synthetic text.
- Verification so far: seven new offline adapter/API tests cover estimates,
  BPM, plan reuse, short/over-limit targets, supplied/invalid scores, invalidation,
  expiry, capability/setup gates and cancellation. Browser checks cover the wait,
  suggested duration, automatic mode, stale/expired results, reused-plan requests
  and mobile layout; screenshots inspected. No JavaScript errors.
- Limits: the estimate describes this plan, not guaranteed lyric adherence or
  exact audio duration. The current complete-song target limit is 330 seconds.
  Closing/reloading the browser requires a fresh analysis; server restart and
  cache expiry also require one. No word-count formula is presented as a forecast.
- Native check with synthetic input: Q8_0/F16, seed 20261011, requested 120 BPM.
  Analysis took 8.06 s; its 37.00 s plan suggested a 40 s target. Creation reused
  that score and took 25.18 s; final WAV 36.44 s, EOS observed, no truncation.
  Exactly one ABC call, one semantic call and one audio call. Isolated runtime
  and local artifacts: `outputs/checks/duration-analysis/20261011-184342/`.
  Listening acceptance is pending; EOS is not claimed as musical acceptance.
- Baseline and full checks passed (103 application test executions), along with the browser
  flow. The user approved PR #20 for merge. README now explains the wait,
  analysis/review/create steps, duration modes and suggested actions without
  including lyric text or style prompts. It distinguishes main from v0.2.0,
  which predates this feature. Final documentation baseline checks passed.
  The feature is included in v0.3.0. Next step: listening acceptance for the
  synthetic smoke-test WAV, which remains pending.

## Current work: Complete Arrangement rejects a near-target vocal plan

Branch: `fix/hip-hop-arrangement-length-clean`, issue #18; included in this feature branch.

- Reproduced the supplied style and lyrics with the installed YuE2 Q8_0/F16
  profile, seed 1234 and 240 s target. It completed with EOS: 154.56 s audio from
  a 154.52 s plan (94 bars at 73 BPM). This confirms the prompt itself is valid;
  the default 240 s target succeeds and is reported as shorter than target.
- At a 120 s target, the same input failed before semantic composition. Planner
  seeds 1234/1235/1236 in one run required 127 s at 73 BPM, 159 s at 100 BPM,
  and 187 s at 95 BPM. The error showed the last, longest attempt instead of
  the shortest plan, obscuring how close the best candidate was to fitting.
- A separate real run with the correct 120 s UI request and 135 s hard cap
  showed why duration tolerance alone was not enough: the planner made a
  154.52 s score at 73 BPM despite the explicit 100 BPM in the style. At 73 BPM,
  its 94 mostly vocal bars could not be shortened to fit the cap without
  deleting vocals.
- Generated scores now honor one unambiguous BPM in the user's style. The same
  score becomes 112.8 s at 100 BPM, keeping every vocal bar and fitting the
  120 s target. If every seed remains too long, the error reports the shortest
  measured plan and tempo.
- Verification: synthetic regression tests check tempo override, EOS handling,
  and shortest-plan diagnostics. The private prompt is not stored in the repo.
  Full real inference at a 120 s target / 135 s cap completed with EOS in
  112.76 s at 100 BPM, seed 1234, without truncation. Before the fix, the
  240 s run ended cleanly at 154.56 s at 73 BPM and was labelled shorter than
  target; the 240 s setting itself was not the failing case.
- Limits: tempo is changed only when the style names one unambiguous BPM; an
  unspecified or ranged BPM keeps the planner tempo. Long vocal passages may
  still need a longer target or shorter lyrics. The new 112.76 s result has not
  received a listening review for that saved test WAV. The user confirmed that
  the fixed workflow works in their own test.
- Next step: update issue #18 and review the resulting PR.

## Current work: delete a song

- Song details have a Delete button with a confirmation. `DELETE /api/songs/{song}`
  removes the WAV, metadata, the artifacts listed in the metadata, the semantic
  token cache and `stems/<song>/`. Files are removed by name, never by a pattern,
  so a song named `a.b` survives deleting `a`. The metadata goes last, so a failed
  delete still lists the song. Deleting the playing song stops the player.
- A queued or running separation/stem edit of the song blocks the delete (409).
- Verification: API test (only the song's files go, sibling kept, job blocks,
  unsafe names refused) and a browser check (cancel keeps it, confirm removes it).
- Limits: no undo or trash. Failed generation reports (`.failure-report`) are not
  library songs and are not touched.

## Current work: optional lyrics and instrumental songs

- Lyrics are optional in the API, CLI (`--lyrics` no longer required) and UI.
  Empty lyrics are sent as-is; audio.cpp only requires a style.
- New Instrumental switch (Create page, `--instrumental` in the CLI), shown only
  when the model declares the `instrumental` capability.
- Observed with YuE2 Q8_0, 30 s clips, vocal stem measured with BS-RoFormer:
  `[instrumental]` lyrics alone were not enough. Direct: vocals at -24 dB RMS
  (mix -17.7 dB). Planned scores with vocal notes were sung: Full score -29 dB,
  Melody -30 dB. A score with no vocal notes gave -80 dB.
- So YuE2 instrumental songs plan a score, replace the vocal line with rests,
  and render that score. Same prompts after the change: Full score silent
  (digital zero), Melody -70 dB, 60 s complete arrangement -77 dB, 60.6 s,
  ended by the model. Muting happens before duration fitting, otherwise the
  planner's vocal bars cannot be shortened (the first 60 s attempt failed).
- Verification: adapter tests (muted score rendered and saved, target fitting
  after muting), request and API capability tests, browser check of the switch.
  Full checks pass. Listening check: not done yet; files are
  `outputs/instrumental-v2-*.wav`.
- Limits: instrumental needs planning, so it is slower (63 s for a 30 s clip
  with Full score). Edit "new" variations of instrumental songs keep the muted
  score, so they change the performance but not the notes. No requirement
  ledger entry yet: it needs an issue link.
- Next step: listening check, then decide whether to offer the upstream
  instrumental LoRA as an optional, license-gated download.

## Current work: parallel model setup in Settings

- Before: one model setup at a time; every Settings card was disabled while any
  download ran. Now each model has its own setup, so different models download
  and verify in parallel. Only that model's buttons are disabled.
- A new setup is refused while another running setup is for the same model or
  writes any of the same files (the separation models share `sep/`).
  Runtime tests still run one at a time through the provider lock.
- Verification: a model test with two parallel setups and two refused ones;
  full checks and the browser flow pass. No real parallel download was run.
- Limits: the free-space check is per setup, so parallel downloads can
  together need more space than is free. A full disk fails the download and
  keeps the resumable `.part` file.
- Next step: reserve the bytes of running setups in the space check if this
  happens in practice.

## Current work: choose the listening address

- `./studio.sh --host <address>` (and `python -m studio.launch --host`) sets the
  address the UI listens on. The default stays `127.0.0.1`. Any other address
  prints a warning that the studio has no login. With `0.0.0.0` the startup line
  says it listens on every network interface and points at `127.0.0.1` for the
  browser, since `0.0.0.0` is not an address a browser can open. audio.cpp engines still listen on `127.0.0.1`.
- README explains the risk, suggests a trusted LAN or Tailscale address, and an
  SSH tunnel for private remote use.
- Verification: launch test (default, `0.0.0.0`, IPv4 and IPv6 addresses, warning),
  now part of the full checks through the bootstrap requirement. Real run on this
  Mac: with `--host 0.0.0.0` the API answered on the LAN address; with the default
  the LAN address refused connections. A manual test with `./studio.sh --host`
  also worked.
- Limits: no login or HTTPS. Do not use `0.0.0.0` on untrusted networks.
- Next step: add authentication only if the studio is shared with other people.

## Current work: complete songs shorter than the target

- Observed: three target-mode jobs failed with "did not finish near the requested
  duration" although every composing attempt ended with EOS. Plans were shorter
  than the target (177.8/256.5/228.8 s for 240/330/330 s targets), and the model
  followed them (175.7/254.8/228.8 s). Fitting only shortens plans, and the
  acceptance check rejected the short side too, after two composing passes.
- Now a complete stream within max(15 s, 12.5%) of the planned duration is
  accepted when it is shorter than the target, rendered, labelled **Shorter than
  target** and explained. Endings far before the plan, capped streams and long
  streams are still rejected. All three failures above would be accepted.
- Verification: ending tests (accepted near the plan, rejected far before it) and
  a browser check for the badge. Full checks pass. Real generation
  `20261011-092721-lux-in-tenebris`: 330 s target, 221.3 s plan, 219.2 s song
  ended by the model, accepted at the first attempt and labelled shorter than
  target. The listening check confirmed a correct musical ending.
- Observed from the saved plans: vocal bars alone take 158-212 s for 201-232
  words, so fitting cannot get these lyrics near 60-120 s. Plans followed a BPM
  written in the style (110 BPM requested, 108-110 planned).
- Next step: decide whether to test tempo scaling of the plan to shorten songs
  while keeping all lyrics.

## Current work: FLAC and MP3 downloads

- The song details drawer offers WAV, FLAC and MP3. `GET /api/export/{song}?format=flac|mp3`
  converts the WAV on request with `soundfile` (bundled libsndfile 1.2.2; LGPL,
  dynamically linked). Nothing is written to `outputs/`.
- FLAC is lossless 16-bit. MP3 is 320 kbps CBR. A 238.7 s, 48 kHz stereo song
  (44.8 MB WAV) became 24.1 MB FLAC in 0.3 s and 9.5 MB MP3 in 1.9 s on an M5 Max.
- libsndfile's MP3 encoder distorts int16 input (2.7 dB SNR, +20 to +36 dB noise
  above 16 kHz on a real song), so MP3 is encoded from float samples. That gives
  40.7 dB SNR, the same as ffmpeg/LAME at 320 kbps. FLAC stays int16 (bit-exact).
- Verification: offline API test (FLAC samples identical to the WAV, MP3 rate,
  channels, length and a clean test tone, WAV unchanged, 404 and 422) and a browser check of the
  drawer links with real encoding. Full checks pass. The fixed MP3 passed a
  listening check in the running studio.
- Limits: the card and player icons still download WAV. Stems, tags and MP3
  bitrate choice are not supported.
- Next step: export stems from Studio Mode through the same endpoint if needed.

## Current work: stop a generation

- `POST /api/jobs/{id}/cancel` removes a queued job of any kind, or stops a
  running generation. Job cards show a stop button; cancelled jobs leave the list.
- audio.cpp has no request cancellation, so `AudioCppProvider.cancel` terminates
  the generation engine. The worker marks the job `cancelled`, not `error`, and
  no song or failure report is written. Steps of a multi-step YuE2 generation
  check the stop request before each engine call, also after an engine restart.
- Verification: offline API test with a blocking fake provider (queued and
  running jobs, no output written), a provider test for a stop during engine
  start, and a browser check for the stop button. Full checks pass. A real
  audio.cpp generation was stopped in `./studio.sh` on macOS (Metal) 5 s after
  it started; it ended `cancelled` with no output, and the next generation
  restarted the engine and finished a song (about 3 minutes).
- Limits: the next job pays the model load again. Running separation and stem edits cannot be stopped yet;
  they run several engine calls that do not check the stop request.
- Next step: allow stopping running separations and stem edits.

## Current work: manual release build

Branch: `feat/manual-release-build`, based on main after PR #9.

- Added `release.sh` (entry point) and `scripts/release.py` (all steps): preflight,
  repository checks, version bump, `CHANGELOG.md` entry, README release block,
  release commit and tag, artifacts, push, GitHub release and asset verification.
- Versioning comes from `pyproject.toml`. `./release.sh patch|minor|major` bumps
  it; an explicit version such as `0.2.0` sets it; the current version can be
  released as-is while it has no tag yet, which is how the first release is made.
- Release notes are generated offline with `git log --first-parent`: merged pull
  requests use their PR title and their branch prefix (`feat/`, `fix/`, `docs/`,
  `test/`, `chore/`) for the section, and commits made directly on `main` are
  categorized from their subject. No API call is needed to build the notes.
- Artifacts are built from the tag itself: a source ZIP with the
  `lux-in-music-<version>/` prefix (the folder the installation guide asks for),
  the wheel, the sdist and `SHA256SUMS.txt`. The script then reads the published
  release back and fails if an asset is missing or empty.
- README gained "Releases and changelog" with the latest version and download
  links, refreshed between `<!-- release:start -->` / `<!-- release:end -->`
  markers; step 2 of the installation guide now downloads the release ZIP instead
  of the moving source. `CHANGELOG.md` was added. AGENTS.md and CONTRIBUTING.md
  document the command and the release-note conventions.
- The script refuses to run on a dirty tree, away from `main`, when `main` is not
  in sync with `origin/main`, when the tag exists, when `dist/` is not ignored, or
  when Git has no `user.name`/`user.email`. `--dry-run` prints everything and
  writes nothing, `--no-push` stops after the local build.
- Verification: `python3 scripts/check.py` passes with the new files. The whole
  flow was exercised end to end on a clone with a local bare remote (first
  release at the current version, then a patch release): correct range from the
  previous tag, correct `CHANGELOG.md` ordering, no duplicate sections when a step
  is re-run, README markers replaced rather than duplicated, executable `studio.sh`
  in the ZIP, and matching checksums. Error paths were exercised for a dirty tree,
  another branch, an existing tag and an older requested version.
- Limits: the run itself was tested on Linux; macOS uses the same `git`, `uv` and
  `gh` commands, and the ZIP extracts with `studio.sh` marked executable in the
  archive. `gh release create` and the asset read-back run for the first time on
  the first real release, which is v0.1.0.
- Next step: publish v0.1.0 from `main` and confirm the four downloadable assets,
  then use `./release.sh patch` for follow-up fixes.

## Delivered: simple local installation guide

Branch: `docs/simple-local-installation`, based on main after PR #8.

- Reorganized README around five beginner steps for Apple Silicon: prepare
  Apple's tools, download/extract the GitHub ZIP, enter the folder using Finder
  drag-and-drop, run `./studio.sh`, choose a model in Settings and create the
  first example. Explain startup stages, model downloads, license review,
  reopening, Control + C, file locations and common recovery commands.
- The example starts with the Melodic Techno demo and its four-minute target;
  the genre templates reuse those lyrics. Technical architecture, launch
  options, Linux CPU limitations and contributor commands follow the user guide.
- Checked commands and button names against `studio.sh`, `scripts/setup.sh`,
  `studio/launch.py`, the Finder launcher and Settings UI. Installation behavior
  and model defaults are unchanged. No real setup/download/generation is needed
  for this documentation update.
- Verification passed: portable baseline (five harness tests), five offline
  bootstrap tests, launcher `--help` confirming port/browser flags, and
  `git diff --check`. No fresh real native build is claimed for this doc change.
- The user also requested a playable README preview and explicitly authorized
  uploading only the accepted Complete Demo. Uploaded one 6.49 MB H.264/AAC
  MP4 attachment with a static cover and the full song (about 237.5 seconds,
  48 kHz stereo). Source WAV remains in the local Library; no model files,
  other songs, settings or runtime artifacts were uploaded. The media file is
  an attachment, outside Git history and installation ZIPs.
- Preview attachment: https://github.com/user-attachments/assets/51a82812-f433-4d41-804c-e34d2c7c23a7
  Native GitHub video rendering uses the standalone attachment URL in README.
  Repository access is required while this repository is private.
- GitHub's Markdown renderer returned a native video element with controls.
  Chrome loaded the uploaded 1280×720 media, reported a 237.5-second duration,
  played it and reached the end after seeking to the final seconds, with no
  media error. GitHub starts it muted, so README explicitly says to enable sound.
  This is remote playback verification; human listening acceptance belongs to
  the original full-song test recorded below. No signed media URLs are committed.

## Delivered: Create layout and genre templates

Branch: `feat/create-layout-genre-templates`, based on main after PR #7.
PR #8 is merged into main (`4f744840ed76f804235f4fdc444845914d5af3b7`), with
passing CI, after the user accepted the templates and shared lyric text.

- Create is 520 px wide on large desktop screens (previously 440 px), with
  the remaining width assigned to Library. Medium screens use a bounded
  proportional width; the mobile view stays stacked. Hide library mini-waves
  below 1320 px to keep song titles and actions usable.
- An expandable Genre templates section beneath the existing Melodic Techno
  demo offers five styles: Progressive Metal, Indie Pop, Cinematic Synthwave,
  Soul & R&B, and Jazz Fusion. Following the user's correction, every template
  loads the same lyric text as the Melodic Techno demo with its genre style,
  preserving title, duration, seed and planning. It sends no generation
  request. Selection is highlighted and cleared when the style is edited.
- Portable baseline and full offline harness passed (67 tests). The extended
  isolated Chrome flow passed with no JavaScript errors: all five presets apply,
  load the exact demo lyrics, preserve title/settings and cause no generation requests; the demo remains in
  Create. Layout checked at 1440/1280/1024/900/390 px without horizontal overflow.
  Desktop and mobile screenshots were inspected under `/private/tmp/lux-templates-ui/`.
- No real audio generation was run for this change. These are style starting
  points, not claims of measured musical quality for each genre.

## Delivered: duration-aware song endings (#1)

Branch: `fix/duration-aware-song-endings`, based on merged PR #6.
The technical flow is implemented and verified. The user accepted the linked
test audio on 2026-10-10 with "è perfetta !! bravo". This records human listening
acceptance for that example; the ledger is implemented. PR #7 was merged into
main (`664183745a11ba9b665ad99cb966799c8495d92d`) and issue #1 is closed.
See [song endings](song-endings.md) for the upstream analysis and exact policy.

- Root cause confirmed in three saved songs: plans of 318.72/336.39/286.45 seconds
  were stopped at semantic caps of 180/180/120 seconds. No composition time budget
  reached the old planner. An outro lyric tag alone did not fix that mismatch.
- Complete arrangement now uses a separate target, score-only inspection,
  conservative instrumental shortening, native groups of up to four measures,
  bounded planning and semantic retries, and EOS/duration checks before rendering.
  Vocal bars, breathing rests, tempo and ending bars are retained. Supplied scores
  stay intact. Clip mode retains the hard cap and explicitly labels truncation.
- The UI has target/cap modes, lyric word/ending advice, named job stages and
  ending badges/details. Existing verified profiles receive these capabilities
  without a new probe/download. Original and adapted plans, token attempts,
  composing-stage EOS and forced-render metadata are stored separately. Token
  recovery uses the actual adapted score and recorded semantic retry seed.
- `.venv/bin/python scripts/check.py --full`: passed, 67 tests (five harness and
  62 application tests). Sixteen new checks cover duration, integrity, stages,
  retry bounds, storage, legacy profiles and semantic recovery. Planned-work
  checks now run in the full harness without changing their acceptance status.
- Isolated Chrome flow passed: target/cap controls, Full score selection,
  dense-text/outro guidance, submitted target without cap, unfinished badges,
  plus the previous Settings, library and mixer flows. No JavaScript errors.
  Final screenshot was inspected at `/private/tmp/lux-ending-ui-final/duration-desktop.png`.
- Real Metal semantic trials with existing Q8_0/F16 weights and a 240-second
  adapted score emitted EOS at 237.52 and 237.92 seconds, seeds 454234436/437.
  The earlier one-bar rewrite hit 270 seconds; keeping native groups succeeded.
  Textual duration instructions alone produced overlong/malformed exploratory
  plans, so the implementation checks actual notation instead of relying on them.
- **Full application generation passed:** target 240 seconds, hard limit 270,
  seed 454234436, generated plan 318.72 seconds at 125 BPM, adapted plan 240 seconds
  (41 instrumental bars removed), one successful semantic attempt, EOS after
  5,938 frames, actual WAV 237.5187 seconds, 48 kHz stereo, total wall time 264 s.
  Profile `yue2-3b--q8_0--f16`, weights release `cca74d8980c00f30ab8d52248a367c01ad633ec2`,
  audio.cpp revision `6c3ab9ad4e599a44d287697863b4f8846ef658be`. No new weights or
  active Settings changes. The test runtime was closed after the run.
- Durable local evidence: `outputs/checks/endings/20261010-target-240/` contains
  `target-240.wav`, metadata, source/adapted scores and semantic tokens. WAV SHA-256:
  `089918fc008347c1fbad47ede6260c797588ad8daf9c47f780a905a8308a8446`.
  The last seconds decay from roughly -14 to -61 dBFS; this signal measurement
  supports a quiet tail but does not prove a satisfactory musical ending.
- **Listening acceptance:** after receiving the WAV link, the user reported
  "è perfetta !! bravo" on 2026-10-10. This is user acceptance, not an automated
  listening analysis or a line-by-line lyric audit. The local test record now
  includes that review. New generations still start with `listening_verified=false`.
  PR #7 is merged and #1 is closed. Other styles,
  languages, seeds and BF16/F32 are not covered by this single audio example;
  failures are bounded and explained, not hidden.

The sections below describe the earlier delivered PR #5/#6 work and its evidence.

## Delivered scope

Implementation branches: `feat/model-settings-harness` and
`feat/model-manager-bootstrap`.
Scope: #2 provider/model independence and #3 Settings, licenses, downloads and
precision choices. The user also requested first-run software installation from
`studio.sh`, with visible progress and no automatic model downloads.

The naming cleanup and portable contributor harness are delivered through PR #5;
model setup, provider boundaries and their follow-up fixes are delivered through
PR #6. Natural song endings (#1) remain a separate task.

## Changes

- `studio.sh` runs software-only setup, prepares Python 3.12/locked dependencies,
  installs missing uv locally, and builds the pinned native families when needed.
  Terminal stages and compiler output report progress. Warm startup skips a
  compatible build. Missing Apple compiler tools give an actionable instruction.
- The UI starts with no model or engine and opens Settings first. Library audio
  remains accessible. No active model is chosen or downloaded automatically.
- Shared inputs/results/queue use provider contracts. YuE2 options, semantic
  token rates and editing live in model adapters. Capability declarations control
  which UI inputs are offered. A fake external provider also works without
  local weights, precision or a VAE; no actual MiniMax integration was added.
- Settings offers generation and optional separation models independently.
  Main Q8_0/BF16/Q4_0 and VAE F16/F32 are independent; BF16 is not called FP16.
- The catalog pins release URLs, file sizes, hashes and component license sources.
  Licenses are displayed and acknowledged before transfer. Unknown licenses block
  setup. BS-RoFormer retains the publisher's checkpoint-provenance caveat.
- Downloads show progress, verify files, resume supported ranges, and support
  cancellation/retry. Existing legacy files are verified and reused. Profiles
  are activated only after a short runtime test and persistent settings save;
  failures preserve the last working selection, including failed disk writes.
- Queued jobs, saved songs and stem sets retain their effective profile. Editing
  resolves original profiles; missing/incompatible files require verification.
  Device/backend or binary changes require another test before activation.
- The requirement ledger and CI now cover #2/#3 and software bootstrap. The full
  harness deduplicates shared test selectors while reporting each requirement.

## Verification

- `.venv/bin/python scripts/check.py --full`: passed, 51 tests total (five harness
  regressions and 46 application tests). Only natural-song-ending remains planned.
- Lock consistency check passed offline (21 packages); `git diff --check` passed.
- Fresh Python environment: real `uv sync --frozen --python 3.12` succeeded in
  `/private/tmp/lux-fresh-environment` using the existing lock file.
- Actual warm `NO_OPEN=1 ./studio.sh --port 18000` prepared dependencies, reused
  the existing native build, and served the UI with no active model/engine.
- Cold software bootstrap, local uv installation, warm reuse, and prerequisite
  failure are checked with fake local tools. After the SSH failure follow-up,
  an actual clean native build succeeded in the user's fresh archived copy on
  this Mac. A build on another machine has not been verified.
- Real Metal runtime probe using the already downloaded YuE2 Q8_0/F16 files
  succeeded and returned nonempty audio. No new real model weights were fetched.
  The probe is a compatibility check, not a listening or song-ending test.
- Published hashes and sizes matched all existing Q8_0/F16 YuE2 files and sidecars.
- Read-only browser check of the real catalog: five model cards, F16 VAE default,
  license gating, BF16/F32 selection (~7.79 GB files), library access and mobile
  navigation. No download/activation request was sent for real models.
- Isolated Playwright/Chrome flow passed: Settings first, licenses, BF16/F32,
  fake download/probe/activation, conditional controls, generated library entry,
  mobile navigation, an external profile without weights, unresolved-license
  controls blocked. No JavaScript errors. Screenshots were inspected.

## Limits and next steps

- BF16/F32 and optional separators are not claimed as tested on every device.
  Their actual activation performs the runtime test on the user's computer.
- #1 remains open. YuE2's maximum duration still sets a semantic token cap; it
  does not guide a full composition to a natural ending. Existing evidence:
  a 180-second request reached 4,500 frames and reported semantic truncation while
  score planning completed. Increasing precision is not an established fix.
- Preserve truncation metadata and add composition-ending evidence/listening
  checks when implementing #1. Do not mark it implemented based on a valid WAV.
- Additional providers need concrete adapters, catalog entries and capability
  tests. External service authentication and billing have not been implemented.
- CI runs portable and offline application checks. Native GPU and browser checks
  remain separate. Push and PR checks passed for the final implementation revision.

## First-run SSH failure follow-up

The user tested a fresh source archive while reusing existing model files.
The pinned audio.cpp `.gitmodules` declares `audio.cpp-server-frontends` using
`git@github.com`, so recursive source setup failed without a GitHub SSH key.
The previous fake-installer tests did not reproduce that transport requirement.

Setup now passes GitHub SSH-to-HTTPS rewrites only to the submodule command and
its child processes. This handles both SSH URL forms and already registered URLs
left by a failed `--init`, without changing the global Git configuration.
See [Git's URL rewrite documentation](https://git-scm.com/docs/git-config#Documentation/git-config.txt-urlltbasegtinsteadOf).

A new offline regression runs the setup against a real local Git submodule index
with HTTPS and SSH transports blocked. Both URL forms reach the HTTPS restriction
rather than SSH, and the fixture's global config remains unchanged. The full
harness passes (42 tests). The user's existing temporary checkout successfully
fetched the pinned frontend commit over HTTPS, compiled both native CLI/server
targets from scratch, and started the UI on port 18001. The Settings API reported
`setup_required: true`, with no active model. The test server was stopped after
verification. No model weights were downloaded or selected. The corrected setup
script was also copied into that temporary archive so the user can resume there.

## Separation activation format follow-up

The user's screenshot showed successful YuE2 Q8_0/F16 and SAM Audio activation,
but HTDemucs 4/6 stems and BS-RoFormer failed with an input-rate mismatch:
expected 44,100 Hz, received 48,000 Hz. The native probe generated the same 48 kHz
test input for every separator. The application separation path already used
different rates, so the probe did not exercise the same input contract.

The catalog now declares each separator's input rate/channels and copies them
into its profile. Probes and normal separation use this declaration; older
profiles keep the mode-format fallback. Real native testing exposed a second
probe error after fixing the rate: HTDemucs rejects the generic `seed` option.
The probe now sends only audio to HTDemucs/BS-RoFormer, and text/seed to SAM Audio.
Setup error hints allow retrying verification rather than always suggesting
another download.

- Offline regression checks inspect the actual WAV sent by each native probe,
  permitted request keys, missing input contracts, and a fake separator requiring
  a different rate from the mode default. Full harness: 45 tests passed.
- Real Metal probes with existing Q8_0 files passed for HTDemucs 4 stems,
  HTDemucs 6 stems and BS-RoFormer, each returning nonempty WAV audio at the
  corrected input contract. Results were saved in
  `/private/tmp/lux-separation-probe-results.json`.
- No model weights were downloaded or active Settings changed by these tests.
  Each test runtime was closed afterwards. This is runtime compatibility evidence,
  not a listening test or proof of separation quality on real songs.
- Updated the user's current temporary archive after checking the affected source
  files matched the committed version. The running app needs a restart before
  retrying Verify existing files for those three models. Successful profiles and
  recorded license reviews remain in its settings file.

## Settings persistence and licensing follow-up

The user reported that verification appeared to reset on launch and dropdown
changes. Their stored profiles and fingerprints were still valid: YuE2 and SAM
remained ready. The browser reset to catalog defaults, forgot license checkbox
state, and still offered verification for already verified active profiles.

Settings now restores the active combination and accepted review IDs, retains
acceptance when a dropdown changes within the same license release, and labels
active profiles as Verified. Selecting another verified profile reuses its saved
validation. New files/releases and changed runtime tokens still require checks;
repair explicitly rechecks. Four new offline cases cover restart/reselection,
changed release/runtime/files and explicit repair. Full harness: 49 tests passed.
The isolated browser flow also passed reload/dropdown persistence without
JavaScript errors. The user's temporary app sources were updated; restart is
required to load the new backend.

The requested online license double-check found an additional individual creator
permission in the original GitHub README and MODEL_LICENSE. Personal creators can
monetize outputs; companies need a commercial weight license. The base weight
license remains CC BY-NC 4.0. Links and scope are recorded in
`docs/model-licenses.md`; the pinned GGUF identifier was not relabeled as Apache.

## Model cards and mixer follow-up

The user requested implicit verification in the setup button and no accumulated
setup log above Settings. Each card now owns a single setup action and its progress
or latest relevant error. Active verified separators use the same disabled
Active / Verified state as the generation model. Completed attempts are hidden;
repair is available under Maintenance. An unselected verified combination still
offers activation, and an unverified combination still needs setup.

The YuE2 card now displays the additional individual creator permission and its
immutable GitHub source revision alongside the base weight licenses. Revised
license details require one new acknowledgement; already validated weights/runtime
do not need another probe for that acknowledgement. Two new offline tests cover
the pinned terms and this review/validation distinction. Full harness: 51 tests.

The user's Studio Mode stack trace exposed `set` being used outside its scope in
`trackRow`. It was reached only for songs with editing enabled, which explains
why another song could still open. The renderer now passes the stem set explicitly.
The browser regression opens both a legacy noneditable song and an editable song,
renders two tracks, and opens the edit bar. No JavaScript errors occurred.

The full isolated browser flow also passed active-separator buttons, card progress,
local error/retry handling, hidden maintenance actions and visible creator terms.
Desktop/mobile screenshots were captured; the desktop result was inspected.
The current temporary archive is updated after source comparisons. A restart
loads the changed catalog/backend; a browser reload loads the new UI scripts.

## Hook song references and instrumental output

Songs created with a Hook audio reference now retain the analyzed audio excerpt
as a local song artifact. Song details show the selected Hook mode, melody role,
detected note/tempo summary and a player for the saved excerpt. While a Hook audio
reference is active, Create hides lyrics, locks the Instrumental control on, and
the API enforces instrumental output independently of the browser.

JavaScript syntax checks, Python compilation and the whitespace diff check passed.
The automated test suite was not run for this change.

## Library source filters

Library rows distinguish Vibe and Hook with separate, restrained color accents.
All, Create, Vibe and Hook filters combine with the existing text search. Songs
with both references appear under both source filters; Create includes songs
without either reference. The browser flow covers all four cases and verifies
that the two source badges use different colors. The portable baseline passed
(15 tests). The browser flow could not start because Playwright is not installed
and the environment could not reach PyPI to install it.

## Bundled Hook demo performance

Hook includes a sample recording supplied by Luke, identified in the UI as
performed and recorded by him and not AI-generated. The user can load it through
the same local file-validation and analysis flow as any other recording. The
original 71.65-second WAV is included as a static app asset and in the built wheel.

The left navigation now uses the same Vibe lavender and Hook aqua as the
corresponding Library badges, including their selected and hover states. Browser
coverage checks that navigation and badge colors stay in sync.

## Studio Mode regenerated take labels

Regenerated versions are now shown as small Original and Take labels below the
Mute/Solo and volume controls on the affected track in Studio Mode. Hovering or
focusing a take opens a compact helper with the saved regeneration time range
and its waveform, highlighting the edited region within the full track. The
helper closes on pointer exit, blur, Escape, scrolling or leaving Studio Mode.
It opens below the take label with an opaque panel background, outside the track's
clipping container. The Regenerate button now sits below the optional direction
textarea instead of beside the selection controls.
The top selector contains only separation sets;
choosing a take or Original loads the corresponding stem set and keeps the
parent separation selected above. Browser coverage includes multiple takes on
one track, verifies the control order, hover/focus helper and highlighted range,
checks other tracks have no version labels, and switches between a take and the
original. Full offline checks passed (183 tests). A focused Chrome smoke test
passed desktop/mobile helper position, opaque background, waveform range,
pointer/focus/Escape dismissal, version selection, navigation cleanup and the
Regenerate button position; screenshots were inspected. No JavaScript errors
occurred in that smoke test. The full browser flow reached these Studio checks
but failed later because an Advanced tooltip extends into the sidebar. That
separate layout failure is the next concrete browser regression to resolve.
