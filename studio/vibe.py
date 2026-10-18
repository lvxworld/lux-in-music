"""Optional local EmbeddingGemma installation and image-to-style matching."""

from __future__ import annotations

import hashlib
import io
import importlib.util
from importlib import metadata
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Callable

import numpy as np

from .providers import ROOT

MODEL_CATALOG_PATH = ROOT / "config" / "model-catalog.json"


def load_model_entry(path: Path = MODEL_CATALOG_PATH, model_id: str = "embeddinggemma-2") -> dict:
    """The optional Vibe model is pinned in the shared model catalog, outside music profiles."""
    models = json.loads(path.read_text())["optional_models"]
    return next(model for model in models if model["id"] == model_id)


MODEL = load_model_entry()
MODEL_ID = MODEL["repo"]
REVISION = MODEL["revision"]
LICENSE_ID = MODEL["licenses"][0]["id"]
LICENSE_REVIEW_ID = hashlib.sha256(json.dumps(
    {"model": MODEL["id"], "revision": REVISION, "licenses": MODEL["licenses"]}, sort_keys=True).encode()).hexdigest()
MODEL_URL = f"https://huggingface.co/{MODEL_ID}/tree/{REVISION}"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
# Pillow's own decompression-bomb threshold; the model itself sees well under 1 MP.
MAX_IMAGE_PIXELS = 89_478_485
ANALYSIS_EDGE = 2048
MAX_VIBE_IMAGES = 5
MIN_SENTENCE_TRANSFORMERS = "6.1.0"
log = logging.getLogger("lux_in_music")
CATALOG_PATH = Path(__file__).parent / "data" / "vibe-style-catalog.json"


class VerificationError(RuntimeError):
    pass


def expected_hash(file: dict) -> str:
    return file.get("sha256") or file["git_sha1"]


def file_digest(path: Path, file: dict) -> str:
    """SHA-256 for LFS files, the git blob ID for small files, as in the music catalog."""
    digest = (hashlib.sha256() if file.get("sha256")
              else hashlib.sha1(b"blob " + str(file["size"]).encode() + b"\0"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_mismatches(files: list[dict], siblings) -> list[str]:
    """Compare Hugging Face metadata for the pinned revision with the catalog before downloading."""
    remote = {sibling.rfilename: sibling for sibling in siblings}
    mismatched = []
    for file in files:
        sibling = remote.get(file["path"])
        lfs = getattr(sibling, "lfs", None) or {}
        if (sibling is None or sibling.size != file["size"]
                or (file.get("sha256") and lfs.get("sha256") != file["sha256"])
                or (not file.get("sha256") and sibling.blob_id != file["git_sha1"])):
            mismatched.append(file["path"])
    return mismatched


def normalize(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(value))
    if not np.isfinite(value).all() or not math.isfinite(norm) or norm <= 1e-12:
        raise ValueError("The embedding model returned an invalid vector")
    return value / norm


def bounded_download_progress(done: int | float, total: int | float) -> tuple[int, int]:
    """Return byte progress bounded by the known snapshot size."""
    total_bytes = max(0, int(total))
    return min(max(0, int(done)), total_bytes), total_bytes


def report_snapshot_progress(progress: Callable, description: str,
                             done: int | float, total: int | float) -> None:
    """Report reconstructed model bytes, ignoring transfer and file-count bars."""
    if not description.startswith("Reconstructing"):
        return
    done_bytes, total_bytes = bounded_download_progress(done, total)
    progress(done_bytes, total_bytes, description)


def vibe_runtime_status() -> dict:
    required_modules = ("sentence_transformers", "transformers", "torch", "torchvision",
                        "huggingface_hub", "PIL")
    missing = [module for module in required_modules
               if importlib.util.find_spec(module) is None]
    try:
        installed_version = metadata.version("sentence-transformers")
    except metadata.PackageNotFoundError:
        installed_version = None
    compatible_version = False
    if installed_version:
        from packaging.version import Version
        compatible_version = Version(installed_version) >= Version(MIN_SENTENCE_TRANSFORMERS)
    return {"installed_version": installed_version,
            "compatible": not missing and compatible_version,
            "missing": missing}


def load_catalog(path: Path = CATALOG_PATH) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("entries")
    if not isinstance(data, list) or len(data) < 30:
        raise ValueError("The Vibe style catalog must contain at least 30 entries")
    seen = set()
    for item in data:
        if not all(isinstance(item.get(key), str) and item[key].strip()
                   for key in ("id", "visual", "style")):
            raise ValueError("Each Vibe catalog entry needs an id, visual description, and style")
        if item["id"] in seen:
            raise ValueError("Vibe catalog IDs must be unique")
        seen.add(item["id"])
    return data


def rank_catalog(image_vector: np.ndarray, catalog_vectors: np.ndarray,
                 catalog: list[dict]) -> dict:
    image = normalize(image_vector)
    matrix = np.asarray(catalog_vectors, dtype=np.float32)
    if matrix.ndim != 2 or len(matrix) != len(catalog) or matrix.shape[1] != image.size:
        raise ValueError("Image and catalog embedding dimensions do not match")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.isfinite(matrix).all() or np.any(norms <= 1e-12):
        raise ValueError("The catalog contains an invalid embedding")
    similarities = (matrix / norms) @ image
    index = min(range(len(catalog)), key=lambda i: (-float(similarities[i]), catalog[i]["id"]))
    return catalog[index]


def blend_catalog(image_vectors, catalog_vectors, catalog):
    """Blend real image matches around a shared semantic direction."""
    vectors = np.asarray([normalize(vector) for vector in image_vectors], dtype=np.float32)
    if not 1 <= len(vectors) <= MAX_VIBE_IMAGES:
        raise ValueError("Choose between 1 and 5 images")
    matches = [rank_catalog(vector, catalog_vectors, catalog) for vector in vectors]
    primary = rank_catalog(vectors.mean(axis=0), catalog_vectors, catalog)
    textures = []
    seen = {primary["id"]}
    for match in matches:
        if match["id"] not in seen:
            seen.add(match["id"])
            for part in match["style"].rstrip(".").split(",")[1:3]:
                part = part.strip()
                if part and part.casefold() not in {text.casefold() for text in textures}:
                    textures.append(part)
    style = primary["style"]
    if textures:
        style = style.rstrip(".") + "; complementary textures: " + ", ".join(textures)
        style += "; cohesive arrangement, evolving instrumental layers, space between contrasting sections."
    pairs = [1 - float(vectors[i] @ vectors[j]) for i in range(len(vectors)) for j in range(i)]
    return {"id": primary["id"], "style": style, "mood": primary.get("mood"), "visual": primary.get("visual"),
            "entry_ids": [match["id"] for match in matches],
            "diversity": float(np.clip(np.mean(pairs), 0, 1)) if pairs else 0.0}


def validate_image(data: bytes):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Choose an image no larger than 20 MB")
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as image:
            # Phone and camera JPEGs with extra pictures are reported as MPO.
            if image.format not in {"JPEG", "MPO", "PNG", "WEBP"}:
                raise ValueError("Use a JPG, PNG, or WebP image")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("The image is too large to analyze (maximum 89 megapixels)")
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.draft("RGB", (ANALYSIS_EDGE, ANALYSIS_EDGE))  # JPEG only: decode at reduced scale
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.load()
            image.thumbnail((ANALYSIS_EDGE, ANALYSIS_EDGE))
            return image.copy()
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("The selected file is not a valid JPG, PNG, or WebP image") from error


class LocalEmbeddingRuntime:
    """Lazy offline-only model loader. One instance is held by VibeManager."""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model = None
        self.catalog_vectors = None
        self.catalog = None
        self._lock = threading.Lock()

    def _load(self, force_cpu=False):
        if self.model is not None:
            return
        runtime = vibe_runtime_status()
        if not runtime["compatible"]:
            version = runtime["installed_version"] or "not installed"
            raise RuntimeError(f"Vibe needs Sentence Transformers {MIN_SENTENCE_TRANSFORMERS} or newer; "
                               f"{version} is installed. Open Settings and select Update Vibe runtime.")
        # A local directory with local_files_only=True needs no network. Do not set
        # HF_HUB_OFFLINE here: huggingface_hub reads it once at import, so it would
        # block later Settings downloads (verify/repair) until Lux restarts.
        from sentence_transformers import SentenceTransformer
        import torch
        devices = (["mps", "cpu"] if not force_cpu and torch.backends.mps.is_available() else ["cpu"])
        catalog = load_catalog()
        signature = hashlib.sha256((REVISION + CATALOG_PATH.read_bytes().decode() +
            "clustering-768-v1").encode()).hexdigest()
        cache_path = self.model_path.parent / f"catalog-{signature}.npy"
        last_error = None
        for device in devices:
            try:
                model = SentenceTransformer(str(self.model_path), device=device,
                    model_kwargs={"torch_dtype": torch.float32},
                    config_kwargs={"audio_config": None}, local_files_only=True)
                model.eval()
                vectors = None
                if cache_path.is_file():
                    try:
                        cached = np.load(cache_path, allow_pickle=False)
                        if cached.shape == (len(catalog), 768) and np.isfinite(cached).all():
                            vectors = np.asarray(cached, dtype=np.float32)
                    except (OSError, ValueError):
                        pass
                    if vectors is None:
                        cache_path.unlink(missing_ok=True)
                if vectors is None:
                    vectors = model.encode([row["visual"] for row in catalog], prompt_name="Clustering",
                        convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
                    vectors = np.asarray(vectors, dtype=np.float32)
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    temp = cache_path.with_suffix(".tmp.npy")
                    np.save(temp, vectors, allow_pickle=False)
                    temp.replace(cache_path)
                if vectors.shape != (len(catalog), 768) or not np.isfinite(vectors).all():
                    cache_path.unlink(missing_ok=True)
                    raise ValueError("The local model produced an incompatible catalog embedding")
                self.model, self.catalog, self.catalog_vectors = model, catalog, vectors
                return
            except Exception as error:
                last_error = error
                if device != "mps":
                    raise
                if "model" in locals():
                    del model
                if hasattr(torch, "mps"):
                    torch.mps.empty_cache()
        raise last_error

    def _encode_image(self, image):
        try:
            return self.model.encode({"image": image}, convert_to_numpy=True,
                                          normalize_embeddings=True, show_progress_bar=False)
        except Exception:
            if not str(getattr(self.model, "device", "")).startswith("mps"):
                raise
            model, self.model = self.model, None
            self.catalog = self.catalog_vectors = None
            del model
            import torch
            torch.mps.empty_cache()
            self._load(force_cpu=True)
            return self.model.encode({"image": image}, convert_to_numpy=True,
                                          normalize_embeddings=True, show_progress_bar=False)

    def analyze(self, image) -> dict:
        return self.analyze_many([image])

    def analyze_many(self, images) -> dict:
        with self._lock:
            self._load()
            vectors = []
            for image in images:
                if len(vectors) >= MAX_VIBE_IMAGES:
                    raise ValueError("Choose up to 5 images")
                vectors.append(self._encode_image(image))
            return blend_catalog(vectors, self.catalog_vectors, self.catalog)

    def close(self):
        with self._lock:
            model, self.model = self.model, None
            self.catalog_vectors = None
            self.catalog = None
            if model is not None:
                try:
                    import torch
                    used_mps = str(getattr(model, "device", "")).startswith("mps")
                    del model
                    if used_mps and torch.backends.mps.is_available():
                        torch.mps.empty_cache()
                except Exception:
                    pass


class VibeManager:
    def __init__(self, root: Path | None = None, downloader: Callable | None = None,
                 files: list[dict] | None = None):
        self.root = root or Path(os.environ.get("LUX_VIBE_DIR", Path.cwd() / "models" / MODEL["install_dir"]))
        self.model_path = self.root / REVISION
        self.state_path = Path.cwd() / ".lux" / "vibe" / "state.json"
        self.files = MODEL["files"] if files is None else files
        self.downloader = downloader or self._download_snapshot
        self.lock = threading.RLock()
        self.job = None
        self.runtime = None
        self._hash_verified_signature = None

    def _read_state(self):
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return {}

    def status(self):
        with self.lock:
            state = self._read_state()
            runtime = vibe_runtime_status()
            return {"model_id": MODEL_ID, "name": MODEL["name"], "revision": REVISION,
                "license": LICENSE_ID, "licenses": MODEL["licenses"],
                "license_review_id": LICENSE_REVIEW_ID, "model_url": MODEL_URL,
                "model_card_url": MODEL["model_card_url"],
                "total_bytes": sum(file["size"] for file in self.files),
                "license_accepted": (state.get("license") == LICENSE_ID
                    and state.get("license_review_id") == LICENSE_REVIEW_ID),
                "installed": self._verified(state),
                "runtime_compatible": runtime["compatible"],
                "runtime_version": runtime["installed_version"],
                "runtime_missing": runtime["missing"],
                "files_present": any((self.model_path / file["path"]).is_file() for file in self.files),
                "job": dict(self.job) if self.job else None}

    def _verified(self, state=None):
        """Cheap check: every pinned file was hashed at install and is unchanged since."""
        state = state or self._read_state()
        manifest = state.get("manifest") or {}
        if (not state.get("ready") or state.get("revision") != REVISION
                or state.get("license_review_id") != LICENSE_REVIEW_ID):
            return False
        for file in self.files:
            path, saved = self.model_path / file["path"], manifest.get(file["path"], {})
            if (not path.is_file() or path.stat().st_size != file["size"]
                    or path.stat().st_mtime_ns != saved.get("mtime_ns")
                    or saved.get("hash") != expected_hash(file)):
                return False
        return bool(self.files)

    def _signature(self):
        return tuple((file["path"], path.stat().st_size, path.stat().st_mtime_ns)
                     for file in self.files if (path := self.model_path / file["path"]).is_file())

    def _verify_hashes(self, state=None):
        """Full check against the pinned catalog hashes, cached per process by file fingerprint."""
        signature = self._signature()
        if len(signature) != len(self.files):
            return False
        if signature == self._hash_verified_signature:
            return True
        if any(file_digest(self.model_path / file["path"], file) != expected_hash(file) for file in self.files):
            return False
        self._hash_verified_signature = signature
        return True

    def start_install(self, license_review_id: str, accepted: bool):
        if license_review_id != LICENSE_REVIEW_ID or not accepted:
            raise ValueError("Review and accept the EmbeddingGemma license before downloading")
        with self.lock:
            if self.job and self.job.get("status") in {"queued", "running"}:
                return dict(self.job)
            job = {"id": uuid.uuid4().hex, "status": "queued", "stage": "queued",
                   "completed_bytes": 0, "total_bytes": 0}
            self.job = job
            threading.Thread(target=self._install, args=(job,), daemon=True).start()
            return dict(job)

    def _install(self, job):
        with self.lock:
            job.update(status="running", stage="downloading")
        runtime_updated = False
        try:
            job.update(stage="preparing_runtime")
            runtime = vibe_runtime_status()
            if not runtime["compatible"]:
                uv = shutil.which("uv")
                if not uv:
                    raise RuntimeError("Install uv, restart Lux, then update the Vibe runtime. Model files are already local.")
                job.update(stage="updating_runtime")
                # Keep the interpreter and packages of the running environment;
                # otherwise uv may recreate .venv under Lux while it is running.
                prepared = subprocess.run([uv, "sync", "--frozen", "--inexact", "--extra", "vibe",
                                           "--python", sys.executable],
                    cwd=Path(__file__).parent.parent,
                    capture_output=True, text=True, timeout=3600)
                if prepared.returncode:
                    log.error("uv sync for the Vibe runtime failed:\n%s", prepared.stderr[-4000:])
                    raise RuntimeError("Could not update the local Vibe runtime. Check network access and disk space, then retry.")
                runtime_updated = True
                runtime = vibe_runtime_status()
                if not runtime["compatible"]:
                    job.update(stage="checking_runtime")
                    raise RuntimeError(f"Vibe needs Sentence Transformers {MIN_SENTENCE_TRANSFORMERS} or newer; "
                                        f"the installed version is {runtime['installed_version'] or 'missing'}. "
                                        "Update the Vibe runtime in Settings, then restart Lux.")
            job.update(stage="downloading")
            self.model_path.mkdir(parents=True, exist_ok=True)
            total = sum(file["size"] for file in self.files)
            if self._verified(self._read_state()) and self._verify_hashes():
                job.update(completed_bytes=total, total_bytes=total,
                           file="Verified local model files")
            else:
                self.downloader(self.model_path, lambda done, total, file:
                    job.update(completed_bytes=done, total_bytes=total, file=file))
                job.update(stage="verifying")
                manifest = {}
                for file in self.files:
                    path = self.model_path / file["path"]
                    if not path.is_file() or path.stat().st_size != file["size"]:
                        raise VerificationError(f"The model download is incomplete: {file['path']}. Retry the download.")
                    job.update(file=file["path"])
                    if file_digest(path, file) != expected_hash(file):
                        # Remove the bad copy so a retry downloads it again instead of trusting local metadata.
                        path.unlink(missing_ok=True)
                        raise VerificationError(f"Checksum mismatch: {file['path']}. Retry to download a verified copy.")
                    manifest[file["path"]] = {"size": file["size"], "mtime_ns": path.stat().st_mtime_ns,
                                              "hash": expected_hash(file)}
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                self.state_path.write_text(json.dumps({"ready": True, "revision": REVISION,
                    "license": LICENSE_ID, "license_review_id": LICENSE_REVIEW_ID,
                    "manifest": manifest}, indent=2))
                self._hash_verified_signature = self._signature()
            job.update(status="done", stage="restart_required" if runtime_updated else "done",
                       restart_required=runtime_updated, completed_bytes=total, total_bytes=total)
        except Exception as error:
            log.exception("Vibe install failed at stage %s", job.get("stage"))
            message = str(error)
            if isinstance(error, VerificationError):
                pass
            elif job.get("stage") in {"preparing_runtime", "updating_runtime"}:
                message = "Could not prepare the local Vibe runtime. Check network access and disk space, then retry."
            elif job.get("stage") == "checking_runtime":
                message = str(error)
            elif any(marker in message.lower() for marker in ("gated", "401", "403", "access denied")):
                message = ("Hugging Face requires access to this model. Open the model page, accept its access terms, "
                           "sign in in Terminal with `hf auth login`, then retry.")
            else:
                message = "Model files could not be downloaded or verified. Check network access and Hugging Face model access, then retry."
            job.update(status="error", stage="error", error=message)

    def _download_snapshot(self, destination: Path, progress: Callable):
        from huggingface_hub import HfApi, snapshot_download
        # Snapshot contains the pinned model artifacts only. No repository code is copied into Lux.
        from tqdm.auto import tqdm
        progress_lock = threading.Lock()
        model_info = HfApi().model_info(MODEL_ID, revision=REVISION, files_metadata=True)
        mismatched = source_mismatches(self.files, model_info.siblings or [])
        if mismatched:
            raise VerificationError("The files published for this model revision do not match the pinned "
                                    f"catalog: {', '.join(mismatched)}. Nothing was downloaded.")
        expected_total = sum(file["size"] for file in self.files)
        class ProgressBar(tqdm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
            def update(self, n=1):
                result = super().update(n)
                # snapshot_download creates several kinds of bars: network bytes,
                # reconstructed bytes, and a file-count bar. Only reconstructed
                # bytes represent completed model files; summing all bars mixes
                # units and can display more than 100%.
                description = str(self.desc or "")
                if description.startswith("Reconstructing"):
                    with progress_lock:
                        report_snapshot_progress(progress, description, self.n, expected_total)
                return result
            def close(self):
                super().close()
        snapshot_download(repo_id=MODEL_ID, revision=REVISION, local_dir=str(destination),
                          tqdm_class=ProgressBar, allow_patterns=[file["path"] for file in self.files])
        progress(expected_total, expected_total, "Verifying model files")

    def analyze(self, image):
        return self.analyze_many([image])

    def analyze_many(self, images):
        state = self._read_state()
        if not self._verified(state) or not self._verify_hashes(state):
            raise RuntimeError("EmbeddingGemma is not installed. Open Settings to install it.")
        if self.runtime is None:
            with self.lock:
                if self.runtime is None:
                    self.runtime = LocalEmbeddingRuntime(self.model_path)
        return self.runtime.analyze_many(images)

    def release(self):
        with self.lock:
            runtime, self.runtime = self.runtime, None
        if runtime:
            runtime.close()


_manager = None
_manager_lock = threading.Lock()


def get_vibe_manager() -> VibeManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = VibeManager()
        return _manager
