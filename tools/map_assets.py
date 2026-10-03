"""Crop game screenshots, review OCR names, and sync approved cards to the website."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime
import unicodedata

from PIL import Image, ImageChops, ImageOps, ImageStat, UnidentifiedImageError

PROJECT = Path(__file__).resolve().parents[1]
CONFIG = Path(__file__).with_name("map_assets_config.json")
CSV_FIELDS = ["id", "ocr_name", "confidence", "suggestion", "name", "approved", "issues"]
EXTENSIONS = {".png", ".jpg", ".jpeg"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def normalize_name(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def validate_name(name):
    if not name or name in {".", ".."} or name.endswith((".", " ")):
        raise ValueError(f"地图名为空或不合法：{name!r}")
    if any(ord(c) < 32 for c in name) or re.search(r'[<>:"/\\|?*]', name):
        raise ValueError(f"地图名含有文件名禁用字符：{name!r}")
    if len(name.encode("utf-8")) > 240:
        raise ValueError(f"地图名过长：{name!r}")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError(f"地图名是 Windows 保留文件名：{name!r}")
    return name


def inside(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f"路径超出处理目录：{relative}")
    return path


def load_catalog(project):
    catalog = read_json(project / "src/data/maps.json")
    if not isinstance(catalog, list):
        raise ValueError("网站地图数据必须是列表")
    seen = set()
    for item in catalog:
        name = validate_name(item["name"])
        if name.casefold() in seen or item["img"] != f"maps/{name}.png":
            raise ValueError(f"网站数据包含重名或不一致的图片路径：{name}")
        seen.add(name.casefold())
    return catalog


def load_config(path):
    config = read_json(path)
    for key in ["reference_size", "tile_size"]:
        if len(config[key]) != 2 or any(type(v) is not int or v <= 0 for v in config[key]):
            raise ValueError(f"{key} 必须是两个正整数")
    for key in ["start", "gap"]:
        if len(config[key]) != 2 or any(type(v) is not int or v < 0 for v in config[key]):
            raise ValueError(f"{key} 必须是两个非负整数")
    if any(type(config[k]) is not int or not 1 <= config[k] <= 20 for k in ["rows", "cols"]):
        raise ValueError("行列数必须在 1～20 之间")
    if not 0 < config["name_top_ratio"] < 1 or not 0 <= config["confidence_threshold"] <= 1:
        raise ValueError("名称区域和置信度阈值必须在 0～1 之间")
    inset = config.get("name_border_inset", 3)
    if type(inset) is not int or not 0 <= inset < min(config["tile_size"]) / 4:
        raise ValueError("名称栏边框裁切量必须是合理的非负整数")
    return config


def crop_cards(image, config, scale=False):
    reference = tuple(config["reference_size"])
    if image.size != reference:
        if not scale:
            raise ValueError(f"截图尺寸为 {image.size}，配置要求 {reference}；等比例截图可用 --scale，其他布局请修改配置")
        if abs((image.width / image.height) / (reference[0] / reference[1]) - 1) > 0.01:
            raise ValueError("截图比例与配置不符，请为这个布局另建配置")
    sx, sy = image.width / reference[0], image.height / reference[1]
    start_x, start_y = config["start"]
    width, height = config["tile_size"]
    gap_x, gap_y = config["gap"]
    boxes = []
    for row in range(config["rows"]):
        for col in range(config["cols"]):
            x = start_x + col * (width + gap_x)
            y = start_y + row * (height + gap_y)
            box = (round(x * sx), round(y * sy), round((x + width) * sx), round((y + height) * sy))
            if box[2] > image.width or box[3] > image.height or box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError("配置中的裁切区域超出截图边界")
            boxes.append((row + 1, col + 1, box))
    # Validate the whole layout before producing any card.
    return [(row, col, image.crop(box)) for row, col, box in boxes]


def extract_name_strip(card, config):
    """Remove the UI frame and whitespace around the single line of dark name text."""
    scale_x = card.width / config["tile_size"][0]
    scale_y = card.height / config["tile_size"][1]
    inset = config.get("name_border_inset", 3)
    x = max(1, round(inset * scale_x))
    y = max(1, round(inset * scale_y))
    box = (x, round(card.height * config["name_top_ratio"]), card.width - x, card.height - y)
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("名称区域过小，请调整配置")
    strip = card.crop(box)
    ink = strip.convert("L").point(lambda p: 255 if p < 120 else 0)
    bounds = ink.getbbox()
    if bounds is None:
        return None
    strip = strip.crop(bounds)
    strip = ImageOps.expand(strip, border=(4, 3, 4, 3), fill=(229, 231, 236))
    return strip.resize((strip.width * 3, strip.height * 3), Image.Resampling.LANCZOS)


def discover_inputs(inputs):
    files = set()
    for entry in inputs:
        path = Path(entry).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"输入不存在：{path}")
        if path.is_dir():
            files.update(p.resolve() for p in path.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
        elif path.suffix.lower() in EXTENSIONS:
            files.add(path)
        else:
            raise ValueError(f"不支持的输入格式：{path}")
    return sorted(files)


def review_rows(manifest):
    return [
        {"id": i["id"], "ocr_name": i["ocr_name"], "confidence": "" if i["confidence"] is None else f'{i["confidence"]:.4f}',
         "suggestion": i.get("suggestion", ""), "name": i["ocr_name"], "approved": "false", "issues": "; ".join(i["issues"])}
        for i in manifest["items"]
    ]


def write_review(batch, manifest):
    rows = review_rows(manifest)
    with (batch / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    template = Path(__file__).with_name("review_template.html").read_text(encoding="utf-8")
    data = [{"image": i["image"], "source": Path(i["source"]).name, "row": i["row"], "col": i["col"], **r}
            for i, r in zip(manifest["items"], rows)]
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    (batch / "review.html").write_text(template.replace("__REVIEW_DATA__", encoded), encoding="utf-8")


def read_review(path, manifest):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not set(CSV_FIELDS).issubset(reader.fieldnames):
            raise ValueError("核对表缺少必要列")
        rows = list(reader)
    expected = {i["id"] for i in manifest["items"]}
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("核对表的 ID 必须完整对应这个批次，且不能重复")
    for row in rows:
        flag = row["approved"].strip().lower()
        if flag not in {"true", "false", "1", "0", "yes", "no", ""}:
            raise ValueError(f'{row["id"]} 的 approved 应填写 true 或 false')
        row["is_approved"] = flag in {"true", "1", "yes"}
    return rows


def load_manifest(batch):
    manifest = read_json(batch / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("不支持的处理批次版本")
    ids = [i["id"] for i in manifest["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("批次包含重复 ID")
    for item in manifest["items"]:
        image = inside(batch, item["image"])
        if not image.is_file() or digest(image) != item["sha256"]:
            raise ValueError(f'裁切图片已被修改或丢失，请重新生成批次：{item["id"]}')
    return manifest


def recognize(batch, project):
    manifest = load_manifest(batch)
    # Do not replace manual corrections when resuming a failed OCR run.
    if (batch / "review.csv").exists():
        rows = read_review(batch / "review.csv", manifest)
        original = {i["id"]: i["ocr_name"] for i in manifest["items"]}
        if any(r["is_approved"] or r["name"] != original[r["id"]] for r in rows):
            raise ValueError("核对表已有人工作出的修改，请新建批次以避免覆盖")
    cache = project / ".cache"
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache / "paddlex"))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("HF_HOME", str(cache / "huggingface"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache))
    print("加载中文识别模型；首次运行会下载模型文件。", flush=True)
    from paddleocr import TextRecognition
    import numpy as np
    from difflib import get_close_matches

    config = manifest["config"]
    model = TextRecognition(model_name=config["model_name"], device="cpu", enable_mkldnn=False)
    catalog = load_catalog(project)
    known = {normalize_name(i["name"]): i["name"] for i in catalog}
    for index, item in enumerate(manifest["items"], 1):
        with Image.open(inside(batch, item["image"])) as source:
            card = source.convert("RGB")
            strip = extract_name_strip(card, config)
            if strip is None:
                text, score = "", 0.0
            else:
                # Paddle's ndarray input uses OpenCV's BGR channel order.
                result = list(model.predict(input=np.asarray(strip)[:, :, ::-1].copy(), batch_size=1))[0]
                text, score = normalize_name(result["rec_text"]), float(result["rec_score"])
        item["ocr_name"], item["confidence"] = text, score
        issues = []
        if not text:
            issues.append("未识别出名称")
        if score < config["confidence_threshold"]:
            issues.append("识别置信度较低")
        if text not in known:
            issues.append("不在现有地图库中，请确认是否为新地图")
        match = get_close_matches(text, list(known), n=1, cutoff=0.72)
        item["suggestion"] = known.get(text) or (known[match[0]] if match else "")
        item["issues"] = issues
        print(f'[{index}/{len(manifest["items"])}] {item["id"]}: {text or "(空)"} ({score:.3f})', flush=True)
    from collections import Counter
    counts = Counter(i["ocr_name"] for i in manifest["items"] if i["ocr_name"])
    for item in manifest["items"]:
        if counts[item["ocr_name"]] > 1:
            item["issues"].append("批次内名称重复，请选定要保留的卡片")
    manifest["ocr_completed"] = True
    write_json(batch / "manifest.json", manifest)
    write_review(batch, manifest)
    return manifest


def prepare(args):
    project, batch = args.project.resolve(), args.output.resolve()
    config = load_config(args.config)
    files = discover_inputs(args.inputs)
    if not files:
        raise ValueError("没有找到截图")
    if batch.exists():
        raise ValueError(f"输出目录已存在，请换一个批次目录：{batch}")
    # Preflight inputs before creating output. Empty/corrupt files are reported, never treated as images.
    valid, skipped = [], []
    for path in files:
        try:
            if path.stat().st_size == 0:
                raise ValueError("空文件")
            with Image.open(path) as image:
                image.load()
                crop_cards(image, config, args.scale)
            valid.append(path)
        except (UnidentifiedImageError, OSError) as error:
            skipped.append({"source": str(path), "reason": f"无法读取截图：{error}"})
        except ValueError as error:
            if path.stat().st_size:
                raise ValueError(f"{path.name}: {error}") from error
            skipped.append({"source": str(path), "reason": str(error)})
    if not valid:
        raise ValueError(f"没有有效截图（跳过 {len(skipped)} 个空文件或损坏文件）")
    batch.mkdir(parents=True)
    (batch / "tiles").mkdir()
    manifest = {"schema_version": 1, "created_at": datetime.now().astimezone().isoformat(),
                "config": config, "ocr_completed": False, "skipped": skipped, "items": []}
    for source_number, path in enumerate(valid, 1):
        source_sha = digest(path)
        with Image.open(path) as image:
            for row, col, card in crop_cards(image.convert("RGB"), config, args.scale):
                item_id = f"s{source_number:03d}-{source_sha[:8]}-r{row}-c{col}"
                relative = f"tiles/{item_id}.png"
                card.save(batch / relative)
                manifest["items"].append({
                    "id": item_id, "source": str(path), "source_sha256": source_sha, "row": row, "col": col,
                    "image": relative, "sha256": digest(batch / relative), "ocr_name": "", "confidence": None,
                    "issues": ["尚未进行 OCR"], "suggestion": ""
                })
    write_json(batch / "manifest.json", manifest)
    write_review(batch, manifest)
    for item in skipped:
        print(f'跳过 {Path(item["source"]).name}：{item["reason"]}', flush=True)
    print(f'已裁切 {len(valid)} 张截图，共 {len(manifest["items"])} 张卡片。', flush=True)
    if not args.skip_ocr:
        manifest = recognize(batch, project)
    print(f"核对页：{batch / 'review.html'}\n核对表：{batch / 'review.csv'}", flush=True)
    return manifest


def same_pixels(first, second):
    with Image.open(first) as a, Image.open(second) as b:
        return a.size == b.size and a.convert("RGB").tobytes() == b.convert("RGB").tobytes()


def artwork_difference(first, second, config):
    """Compare the central artwork; excludes the difficulty bar and name strip."""
    regions = []
    for path in [first, second]:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            regions.append(rgb.crop((3, round(rgb.height * 0.14), rgb.width - 3,
                                     round(rgb.height * config["name_top_ratio"]) - 3)).resize((128, 64)))
    mean = ImageStat.Stat(ImageChops.difference(*regions)).mean
    return round(sum(mean) / (3 * 255), 5)


def compare_batch(batch, project, review=None):
    from collections import Counter
    manifest = load_manifest(batch)
    rows = read_review(review or batch / "review.csv", manifest)
    items = {i["id"]: i for i in manifest["items"]}
    catalog = load_catalog(project)
    known = {i["name"] for i in catalog}
    names = Counter(row["name"] for row in rows if row["name"])
    records = []
    for row in rows:
        name = row["name"]
        item = items[row["id"]]
        entry = {"id": item["id"], "name": name, "approved": row["is_approved"],
                 "source": item["source"], "image": item["image"], "suggestion": item.get("suggestion", ""),
                 "issues": list(item["issues"]), "artwork_difference": None}
        try:
            validate_name(name)
        except ValueError:
            entry["kind"] = "unrecognized" if not name else "invalid_name"
            records.append(entry)
            continue
        if names[name] > 1:
            entry["issues"].append("名称重复，需要选定要保留的卡片")
        existing = project / "public/maps" / f"{name}.png"
        if name not in known:
            entry["kind"] = "new_name"
        elif not existing.exists():
            entry["kind"] = "missing_image"
        elif same_pixels(batch / item["image"], existing):
            entry["kind"] = "unchanged"
            entry["artwork_difference"] = 0.0
        else:
            entry["kind"] = "image_changed"
            entry["artwork_difference"] = artwork_difference(batch / item["image"], existing, manifest["config"])
        records.append(entry)
    covered = {row["name"] for row in rows}
    confirmed = {row["name"] for row in rows if row["is_approved"]}
    return {
        "summary": dict(Counter(i["kind"] for i in records)),
        "cards": len(records), "confirmed_cards": sum(row["is_approved"] for row in rows), "current_maps": len(known),
        "duplicate_names": sorted(name for name, count in names.items() if count > 1),
        "not_covered": sorted(known - covered),
        "not_confirmed": sorted(known - confirmed),
        "note": "新名称可能是 OCR 错字。图像差异可能来自贴图、界面元素或裁切位置；未覆盖地图不会被自动删除。",
        "items": records,
    }


def sync_batch(batch, project, review=None, replace_existing=False, dry_run=False, renames=None, keep_legacy=False):
    batch, project = batch.resolve(), project.resolve()
    manifest = load_manifest(batch)
    rows = read_review(review or batch / "review.csv", manifest)
    approved = [r for r in rows if r["is_approved"]]
    if not approved:
        raise ValueError("没有确认的地图；请核对图片、填写 name 并将 approved 设为 true")
    items = {i["id"]: i for i in manifest["items"]}
    catalog = load_catalog(project)
    baseline = {i["name"]: dict(i) for i in catalog}
    from pypinyin import lazy_pinyin
    migrations = []
    if renames is not None:
        mapping = read_json(renames)
        if not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()):
            raise ValueError("改名表必须是旧名称到新名称的 JSON 对象")
        original = {i["name"]: i for i in catalog}
        approved_names = {r["name"] for r in approved}
        destinations = set()
        for old, new in mapping.items():
            validate_name(old)
            validate_name(new)
            if old not in original or new not in approved_names or old == new:
                raise ValueError(f"改名必须对应现有地图和已确认的新名称：{old} → {new}")
            if new.casefold() in destinations or new.casefold() in {n.casefold() for n in original}:
                raise ValueError(f"改名目标与现有名称或其他目标冲突：{new}")
            destinations.add(new.casefold())
            old_path = inside(project, f"public/maps/{old}.png")
            new_path = inside(project, f"public/maps/{new}.png")
            if new_path.exists():
                raise ValueError(f"改名目标图片已存在：{new}")
            migrations.append({"old": old, "new": new, "old_path": old_path})
        for migration in migrations:
            entry = original[migration["old"]]
            entry["aliases"] = list(dict.fromkeys([*entry.get("aliases", []), migration["old"]]))
            entry.update(name=migration["new"], img=f'maps/{migration["new"]}.png',
                         pinyin="".join(lazy_pinyin(migration["new"])))
    by_name = {i["name"].casefold(): i for i in catalog}
    seen, plans = set(), []
    for row in approved:
        name = validate_name(row["name"])
        if name.casefold() in seen:
            raise ValueError(f"已确认的地图名称重复：{name}")
        seen.add(name.casefold())
        relative = f"public/maps/{name}.png"
        source = inside(batch, items[row["id"]]["image"])
        target = inside(project, relative)
        existing = by_name.get(name.casefold())
        if existing and name != existing["name"]:
            raise ValueError(f"名称大小写与现有地图冲突：{name}")
        action = "add"
        if target.exists():
            action = "unchanged" if same_pixels(source, target) else "replace"
        if existing and not target.exists():
            action = "restore"
        plans.append({"name": name, "action": action, "source": source, "target": target})
    replacements = [p["name"] for p in plans if p["action"] == "replace"]
    if replacements and not replace_existing:
        raise ValueError("以下名称已有不同图片，整批未写入；确认替换请使用 --replace-existing：" + "、".join(replacements))
    for plan in plans:
        if plan["name"].casefold() not in by_name:
            name = plan["name"]
            entry = {"name": name, "img": f"maps/{name}.png", "pinyin": "".join(lazy_pinyin(name))}
            catalog.append(entry)
            by_name[name.casefold()] = entry
    legacy_plans = []
    if keep_legacy:
        old_names = {m["new"]: m["old"] for m in migrations}
        for plan in plans:
            previous = baseline.get(old_names.get(plan["name"], plan["name"]))
            if previous is None:
                by_name[plan["name"].casefold()]["oldImg"] = None
                continue  # New maps have no historical artwork.
            if "oldImg" in previous and previous["oldImg"] is None:
                continue  # Do not invent old artwork for maps added after the baseline.
            entry = by_name[plan["name"].casefold()]
            if previous.get("oldImg") and previous["oldImg"] != previous["img"]:
                legacy = inside(project, "public/" + previous["oldImg"])
                if not legacy.is_file():
                    raise ValueError(f'旧贴图丢失：{previous["name"]}')
                entry["oldImg"] = previous["oldImg"]
                continue
            old_source = inside(project, "public/" + previous["img"])
            if not old_source.is_file():
                raise ValueError(f'无法保留旧贴图，图片丢失：{previous["name"]}')
            if same_pixels(old_source, plan["source"]):
                entry["oldImg"] = entry["img"]
                continue
            relative = f'maps-legacy/{plan["name"]}.png'
            legacy_target = inside(project, "public/" + relative)
            if legacy_target.exists() and not same_pixels(old_source, legacy_target):
                raise ValueError(f'旧贴图路径已有其他图片，整批未写入：{relative}')
            entry["oldImg"] = relative
            if not legacy_target.exists():
                legacy_plans.append({"source": old_source, "target": legacy_target})
    result = {"dry_run": dry_run, "changes": [{"name": p["name"], "action": p["action"]} for p in plans],
              "map_count": len(catalog), "backup": None,
              "renames": [{"old": m["old"], "new": m["new"]} for m in migrations],
              "legacy_copies": len(legacy_plans)}
    if dry_run:
        return result
    changed = [p for p in plans if p["action"] != "unchanged"]
    data_files = [project / "src/data/maps.json", project / "maps.json"]
    # Preserve existing order and spelling, including the original pinyin.
    needs_json = any(not p.exists() or read_json(p) != catalog for p in data_files)
    if not changed and not needs_json and not legacy_plans:
        return result
    work = project / "work"
    work.mkdir(exist_ok=True)
    backup = work / "backups" / timestamp()
    backup.mkdir(parents=True)
    targets = [p["target"] for p in changed + legacy_plans] + (data_files if needs_json else [])
    retired = [m["old_path"] for m in migrations if m["old_path"].exists()]
    backup_targets = targets + retired
    existed = {p: p.exists() for p in backup_targets}
    for target in backup_targets:
        if existed[target]:
            saved = backup / target.relative_to(project)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    write_json(backup / "changes.json", {**result, "files": [
        {"path": str(p.relative_to(project)), "existed": existed[p]} for p in backup_targets]})
    written = []
    try:
        with tempfile.TemporaryDirectory(prefix="map-sync-", dir=work) as staging:
            staged = Path(staging)
            for plan in changed + legacy_plans:
                path = staged / plan["target"].relative_to(project)
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plan["source"], path)
            if needs_json:
                for target in data_files:
                    path = staged / target.relative_to(project)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    write_json(path, catalog)
            for target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged / target.relative_to(project), target)
                written.append(target)
            for target in retired:
                target.unlink()
                written.append(target)
    except Exception:
        for target in reversed(written):
            if existed[target]:
                shutil.copy2(backup / target.relative_to(project), target)
            else:
                target.unlink(missing_ok=True)
        raise
    result["backup"] = str(backup)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=PROJECT, help="网站仓库路径，默认使用脚本所在仓库")
    commands = parser.add_subparsers(dest="command", required=True)
    crop = commands.add_parser("prepare", help="裁切截图、识别名称、生成核对页")
    crop.add_argument("inputs", nargs="+", help="截图文件或目录，可传多个")
    crop.add_argument("--output", type=Path, default=PROJECT / "work/maps" / timestamp())
    crop.add_argument("--config", type=Path, default=CONFIG)
    crop.add_argument("--scale", action="store_true", help="按参考截图尺寸等比例缩放裁切区域")
    crop.add_argument("--skip-ocr", action="store_true", help="仅裁切，之后可用 ocr 子命令识别")
    ocr = commands.add_parser("ocr", help="对已裁切批次运行 OCR，或重试失败的识别")
    ocr.add_argument("batch", type=Path)
    sync = commands.add_parser("sync", help="同步核对表中已确认的地图")
    sync.add_argument("batch", type=Path)
    sync.add_argument("--review", type=Path, help="核对后的 CSV，默认使用批次中的 review.csv")
    sync.add_argument("--replace-existing", action="store_true", help="允许替换已有图片，写入前自动备份")
    sync.add_argument("--dry-run", action="store_true", help="只检查和展示同步计划")
    sync.add_argument("--renames", type=Path, help="显式旧名称到新名称映射 JSON；保留旧名称别名并备份旧图片")
    sync.add_argument("--keep-legacy", action="store_true", help="为原有地图保留旧贴图，供网站切换；相同图片复用文件")
    compare = commands.add_parser("compare", help="对比新名称、同名图片变化和旧地图库覆盖情况")
    compare.add_argument("batch", type=Path)
    compare.add_argument("--review", type=Path)
    compare.add_argument("--output", type=Path, help="保存对比报告 JSON")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args)
        elif args.command == "ocr":
            recognize(args.batch.resolve(), args.project.resolve())
            print(f"核对页：{args.batch.resolve() / 'review.html'}")
        elif args.command == "compare":
            result = compare_batch(args.batch.resolve(), args.project.resolve(), args.review)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                write_json(args.output, result)
                print(f"对比报告：{args.output.resolve()}")
                print(json.dumps({k: result[k] for k in ["summary", "cards", "current_maps"]}, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            result = sync_batch(args.batch, args.project, args.review, args.replace_existing, args.dry_run, args.renames, args.keep_legacy)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
