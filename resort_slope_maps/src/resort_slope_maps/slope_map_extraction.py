"""Tools used by the ``slope_map_extraction.ipynb`` research notebook.

Le module inventorie les plans conserves par les scrapers, prepare images et PDF, utilise
facultativement Tesseract comme premier passage gratuit, puis demande une extraction JSON
structuree au fournisseur LLM commun du depot. Les resultats sont mis en cache par SHA-256.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageOps
PROMPT_VERSION = 1
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plan_title": {"type": ["string", "null"]},
        "map_scope": {
            "type": "string",
            "enum": ["alpine", "nordic", "mixed", "summer", "unknown"],
        },
        "slopes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "color": {
                        "type": "string",
                        "enum": [
                            "green", "blue", "red", "black", "yellow", "orange",
                            "purple", "other", "unknown",
                        ],
                    },
                    "kind": {
                        "type": "string",
                        "enum": [
                            "alpine", "nordic", "ski_route", "snowpark", "sledge",
                            "pedestrian", "other", "unknown",
                        ],
                    },
                    "sector": {"type": ["string", "null"]},
                    "number": {"type": ["string", "null"]},
                },
                "required": ["name", "color", "kind", "sector", "number"],
                "additionalProperties": False,
            },
        },
        "lifts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": ["string", "null"]},
                    "status": {
                        "type": "string",
                        "enum": ["current", "planned", "closed", "unknown"],
                    },
                    "sector": {"type": ["string", "null"]},
                },
                "required": ["name", "type", "status", "sector"],
                "additionalProperties": False,
            },
        },
        "legend": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["slope", "lift", "activity", "service", "safety", "other"],
                    },
                    "color_or_symbol": {"type": ["string", "null"]},
                },
                "required": ["label", "category", "color_or_symbol"],
                "additionalProperties": False,
            },
        },
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": ["string", "null"]},
                    "sector": {"type": ["string", "null"]},
                    "details": {"type": ["string", "null"]},
                },
                "required": ["name", "type", "sector", "details"],
                "additionalProperties": False,
            },
        },
        "other_information": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "label": {"type": "string"},
                    "value": {"type": ["string", "null"]},
                    "unit": {"type": ["string", "null"]},
                },
                "required": ["category", "label", "value", "unit"],
                "additionalProperties": False,
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "plan_title", "map_scope", "slopes", "lifts", "legend", "activities",
        "other_information", "warnings", "confidence",
    ],
    "additionalProperties": False,
}


def find_project_root(start: Path | None = None) -> Path:
    root = (start or Path.cwd()).resolve()
    for candidate in (root, root / "resort_slope_maps", root.parent):
        if (candidate / "notebooks").is_dir() and (candidate / "data").is_dir():
            return candidate
    raise RuntimeError(
        "Lancez le notebook depuis SkiJo, resort_slope_maps ou resort_slope_maps/notebooks."
    )


def inventory_maps(root: Path, *, latest_only: bool = True,
                   slugs: Iterable[str] | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    wanted = set(slugs or [])
    for manifest in sorted((root / "data").glob("data_*/slopes_map/manifest.jsonl")):
        source = manifest.parent.parent.name.removeprefix("data_")
        for line_number, line in enumerate(manifest.read_text().splitlines(), 1):
            if not line.strip():
                continue
            entry = json.loads(line)
            if wanted and entry.get("slug") not in wanted:
                continue
            file_path = manifest.parent / entry["file"]
            rows.append({
                **entry,
                "source": source,
                "source_key": entry.get("slug"),
                "manifest": str(manifest.relative_to(root)),
                "manifest_line": line_number,
                "file_path": str(file_path),
                "file_exists": file_path.is_file(),
                "suffix": file_path.suffix.lower(),
            })
    columns = [
        "source", "source_key", "slug", "sha256", "file", "file_path", "file_exists",
        "suffix", "bytes", "downloaded_at", "url", "title", "map_id", "manifest",
        "manifest_line",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame:
            frame[column] = pd.NA
    frame["downloaded_at"] = pd.to_datetime(frame["downloaded_at"], errors="coerce", utc=True)
    frame = frame.sort_values(["source", "source_key", "downloaded_at", "manifest_line"])
    if latest_only:
        frame = frame.groupby(["source", "source_key"], dropna=False).tail(1)
    return frame[columns].reset_index(drop=True)


def _resize(image: Image.Image, max_side: int) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) <= max_side:
        return image
    ratio = max_side / max(image.size)
    return image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)


def render_plan(path: Path, *, max_pages: int = 4, pdf_dpi: int = 180,
                max_side: int = 4200, jpeg_quality: int = 90) -> list[tuple[str, bytes]]:
    images: list[Image.Image] = []
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(path)
        scale = pdf_dpi / 72
        try:
            for index in range(min(len(pdf), max_pages)):
                page = pdf[index]
                try:
                    images.append(page.render(scale=scale).to_pil())
                finally:
                    page.close()
        finally:
            pdf.close()
    else:
        with Image.open(path) as source:
            images = [source.copy()]
    encoded: list[tuple[str, bytes]] = []
    for image in images:
        output = io.BytesIO()
        _resize(image, max_side).save(output, "JPEG", quality=jpeg_quality, optimize=True)
        encoded.append(("image/jpeg", output.getvalue()))
    return encoded


def local_ocr(images: list[tuple[str, bytes]], *, max_chars: int = 16_000) -> str:
    executable = shutil.which("tesseract")
    if not executable:
        return ""
    language_output = subprocess.run(
        [executable, "--list-langs"], capture_output=True, text=True, check=False,
    ).stdout
    language = "fra+eng" if "fra" in language_output else "eng"
    pages: list[str] = []
    for page_number, (_, payload) in enumerate(images, 1):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as temporary:
            temporary.write(payload)
            temporary.flush()
            result = subprocess.run(
                [executable, temporary.name, "stdout", "-l", language, "--psm", "11"],
                capture_output=True, text=True, check=False, timeout=120,
            )
        cleaned = "\n".join(line.strip() for line in result.stdout.splitlines() if line.strip())
        pages.append(f"--- page {page_number} ---\n{cleaned}")
    return "\n".join(pages)[:max_chars]


def extraction_prompt(row: pd.Series, ocr_text: str) -> str:
    ocr_section = ocr_text or "(OCR local indisponible ou vide)"
    return f"""Analyse ce plan de pistes de ski et transcris uniquement ce qui est reellement visible.

Objectifs :
1. Lister chaque piste nommee, avec sa couleur et son type. La couleur doit venir du trace,
   d'une pastille ou d'une legende visible ; ne jamais la deduire de la difficulte supposee.
2. Lister chaque remontee mecanique nommee et son type si celui-ci est indique.
3. Transcrire la legende en elements classes.
4. Relever les activites et les autres informations utiles (altitudes, secteurs, services,
   dangers, horaires, contacts, chiffres), sans transformer les simples noms de lieux en pistes.

Regles qualite : conserve l'orthographe du plan, fusionne les doublons evidents entre pages,
n'invente jamais un nom illisible, utilise `unknown` ou null en cas de doute, et decris les
limites dans `warnings`. `confidence` mesure la fiabilite globale de 0 a 1.

Contexte du fichier : source={row.get('source')}, cle={row.get('source_key')},
titre_manifeste={row.get('title')}.

Premier passage OCR, imparfait et seulement fourni comme aide :
{ocr_section}
"""


def _cache_valid(payload: dict[str, Any], sha256: str, model: str) -> bool:
    return (payload.get("sha256") == sha256 and payload.get("model") == model
            and payload.get("prompt_version") == PROMPT_VERSION
            and payload.get("status") == "ok")


async def extract_one(row: pd.Series, *, model: str, cache_dir: Path,
                      use_local_ocr: bool = True, force: bool = False,
                      max_pages: int = 4) -> dict[str, Any]:
    sha256 = str(row["sha256"])
    cache_file = cache_dir / f"{sha256}.json"
    if cache_file.exists() and not force:
        cached = json.loads(cache_file.read_text())
        if _cache_valid(cached, sha256, model):
            cached["from_cache"] = True
            return cached

    images = render_plan(Path(row["file_path"]), max_pages=max_pages)
    ocr_text = local_ocr(images) if use_local_ocr else ""
    from resort_slope_maps.llm_provider import generate_json

    response = await generate_json(
        extraction_prompt(row, ocr_text), EXTRACTION_SCHEMA, model,
        selected_provider="openai", name="slope_map_extraction", timeout=240, images=images,
    )
    payload = {
        "status": "ok",
        "sha256": sha256,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "extracted_at": datetime.now(UTC).isoformat(),
        "from_cache": False,
        "usage": response.usage,
        "ocr_text": ocr_text,
        "extraction": json.loads(response.text),
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


async def run_extractions(inventory: pd.DataFrame, *, model: str, cache_dir: Path,
                          limit: int | None = None, use_local_ocr: bool = True,
                          force: bool = False, continue_on_error: bool = True) -> list[dict[str, Any]]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY est absente de l'environnement.")
    selected = inventory[inventory["file_exists"]].head(limit) if limit else inventory[inventory["file_exists"]]
    records: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        metadata = {
            key: (value.isoformat() if isinstance(value, pd.Timestamp) else value)
            for key, value in row.items() if not pd.isna(value)
        }
        try:
            result = await extract_one(
                row, model=model, cache_dir=cache_dir, use_local_ocr=use_local_ocr, force=force,
            )
        except Exception as error:
            if not continue_on_error:
                raise
            result = {
                "status": "error", "sha256": str(row["sha256"]), "model": model,
                "prompt_version": PROMPT_VERSION, "extracted_at": datetime.now(UTC).isoformat(),
                "error": f"{type(error).__name__}: {error}", "extraction": None,
            }
        records.append({"map": metadata, **result})
        await asyncio.sleep(0)
    return records


def load_cached_records(inventory: pd.DataFrame, cache_dir: Path, model: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in inventory.iterrows():
        cache_file = cache_dir / f"{row['sha256']}.json"
        if not cache_file.exists():
            continue
        payload = json.loads(cache_file.read_text())
        if not _cache_valid(payload, str(row["sha256"]), model):
            continue
        metadata = {
            key: (value.isoformat() if isinstance(value, pd.Timestamp) else value)
            for key, value in row.items() if not pd.isna(value)
        }
        records.append({"map": metadata, **payload, "from_cache": True})
    return records


def load_published_records(path: Path) -> list[dict[str, Any]]:
    """Load sanitized extraction records published with the research project."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _base(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record["map"]
    extraction = record.get("extraction") or {}
    return {
        "plan_sha256": record["sha256"],
        "source": metadata.get("source"),
        "source_key": metadata.get("source_key"),
        "owner_kind": metadata.get("owner_kind"),
        "owner_slug": metadata.get("owner_slug"),
        "owner_name": metadata.get("owner_name"),
        "plan_title": extraction.get("plan_title"),
        "map_scope": extraction.get("map_scope"),
        "confidence": extraction.get("confidence"),
    }


def flatten_records(records: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    specs = {
        "slopes": ("slopes", "slope_index"),
        "lifts_on_maps": ("lifts", "lift_index"),
        "legend": ("legend", "legend_index"),
        "activities": ("activities", "activity_index"),
        "other_information": ("other_information", "information_index"),
    }
    tables: dict[str, pd.DataFrame] = {}
    for table_name, (field, index_name) in specs.items():
        rows: list[dict[str, Any]] = []
        for record in records:
            extraction = record.get("extraction") or {}
            for position, item in enumerate(extraction.get(field) or [], 1):
                rows.append({**_base(record), index_name: position, **item})
        tables[table_name] = pd.DataFrame(rows)
    return tables


_LIFT_WORDS = re.compile(
    r"\b(?:tsd|tsf|tc|tk|tke|tapis|telecabine|telesiege|teleski|telepherique|funiculaire)\b",
)


def normalize_lift_name(value: str | None) -> str:
    text_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text_value = _LIFT_WORDS.sub(" ", text_value.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text_value).split())


def lift_type_group(value: str | None) -> str | None:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    groups = [
        ("carpet", ("tapis", "carpet")),
        ("cable_car", ("telepherique", "cable car")),
        ("funicular", ("funiculaire", "funicular")),
        ("gondola", ("telecabine", "gondola")),
        ("chairlift", ("telesiege", "chair")),
        ("surface", ("teleski", "tire-fesses", "arbalete", "surface", "drag lift")),
        ("rope_tow", ("fil neige", "rope tow")),
    ]
    return next((group for group, words in groups if any(word in normalized for word in words)), None)


def compare_lifts(records: list[dict[str, Any]], database_lifts: pd.DataFrame,
                  *, fuzzy_threshold: float = 0.78) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if database_lifts.empty:
        return pd.DataFrame(rows)
    database_lifts = database_lifts.copy()
    for record in records:
        if record.get("status") != "ok":
            continue
        base = _base(record)
        owner_kind = base.get("owner_kind")
        owner_slug = base.get("owner_slug")
        db = database_lifts[
            (database_lifts["owner_slug"] == owner_slug)
            & (database_lifts["owner_kind"] == owner_kind)
        ].copy()
        db["normalized"] = db["name"].map(normalize_lift_name)
        available = set(db.index)
        plan_lifts = (record.get("extraction") or {}).get("lifts") or []
        for lift in plan_lifts:
            normalized = normalize_lift_name(lift.get("name"))
            candidates = []
            for index in available:
                candidate = db.loc[index]
                score = SequenceMatcher(None, normalized, candidate["normalized"]).ratio()
                candidates.append((score, index))
            score, match_index = max(candidates, default=(0.0, None))
            matched = match_index is not None and score >= fuzzy_threshold
            database_row = db.loc[match_index] if matched else None
            if matched:
                available.remove(match_index)
            map_group = lift_type_group(lift.get("type"))
            db_group = (lift_type_group(database_row["kind_label"])
                        if database_row is not None else None)
            type_match = (map_group == db_group) if map_group and db_group else None
            reasons = []
            if not matched:
                reasons.append("absente_db")
            elif score < 0.90:
                reasons.append("nom_approximatif")
            if type_match is False:
                reasons.append("type_different")
            rows.append({
                **base,
                "comparison_status": "matched" if matched else "map_only",
                "match_score": round(score, 3) if match_index is not None else None,
                "map_lift_name": lift.get("name"),
                "map_lift_type": lift.get("type"),
                "map_lift_group": map_group,
                "map_lift_status": lift.get("status"),
                "db_lift_id": None if database_row is None else database_row["lift_id"],
                "db_lift_name": None if database_row is None else database_row["name"],
                "db_lift_family": None if database_row is None else database_row["family"],
                "db_lift_type": None if database_row is None else database_row["kind_label"],
                "db_lift_group": db_group,
                "type_match": type_match,
                "a_revoir": bool(reasons),
                "review_reason": " | ".join(reasons),
            })
        for index in available:
            database_row = db.loc[index]
            rows.append({
                **base,
                "comparison_status": "db_only", "match_score": None,
                "map_lift_name": None, "map_lift_type": None, "map_lift_group": None,
                "map_lift_status": None,
                "db_lift_id": database_row["lift_id"], "db_lift_name": database_row["name"],
                "db_lift_family": database_row["family"],
                "db_lift_type": database_row["kind_label"],
                "db_lift_group": lift_type_group(database_row["kind_label"]),
                "type_match": None, "a_revoir": True, "review_reason": "absente_plan",
            })
    return pd.DataFrame(rows)


def export_records(records: list[dict[str, Any]], database_lifts: pd.DataFrame,
                   output_dir: Path, working_dir: Path | None = None) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    working_dir = working_dir or output_dir
    working_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    jsonl_path = working_dir / "map_extractions.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(record, ensure_ascii=False, default=str)
                                    for record in records) + ("\n" if records else ""))
    paths["map_extractions"] = jsonl_path
    for name, frame in flatten_records(records).items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    comparison = compare_lifts(records, database_lifts)
    comparison_path = output_dir / "lift_comparison.csv"
    comparison.to_csv(comparison_path, index=False)
    paths["lift_comparison"] = comparison_path
    return paths


def extraction_summary(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        extraction = record.get("extraction") or {}
        rows.append({
            **_base(record),
            "status": record.get("status"),
            "from_cache": record.get("from_cache", False),
            "slopes": len(extraction.get("slopes") or []),
            "lifts": len(extraction.get("lifts") or []),
            "legend_items": len(extraction.get("legend") or []),
            "activities": len(extraction.get("activities") or []),
            "other_information": len(extraction.get("other_information") or []),
            "warnings": " | ".join(extraction.get("warnings") or []),
            "error": record.get("error"),
        })
    return pd.DataFrame(rows)
