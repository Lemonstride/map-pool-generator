"""Create a self-contained old/new screenshot comparison report before syncing."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import shutil

import map_assets as assets

LABELS = {
    "preview_changed": "地图预览变化",
    "ui_only": "仅标记／界面变化",
    "unchanged": "像素相同",
    "new": "新增地图",
}


def build_report(batch, project, review, renames, output, annotations=None):
    manifest = assets.load_manifest(batch)
    rows = assets.read_review(review, manifest)
    catalog = assets.load_catalog(project)
    known = {i["name"]: i for i in catalog}
    mapping = assets.read_json(renames) if renames else {}
    previous = {new: old for old, new in mapping.items()}
    notes = assets.read_json(annotations) if annotations else {}
    items = {i["id"]: i for i in manifest["items"]}
    selected = [r for r in rows if r["is_approved"]]
    names = [r["name"] for r in selected]
    if len(names) != len(set(names)):
        raise ValueError("已确认的地图名称重复")
    if output.exists():
        raise ValueError("报告目录已存在，请换一个目录")
    records = []
    for row in selected:
        name = assets.validate_name(row["name"])
        old_name = previous.get(name, name)
        item = items[row["id"]]
        source = assets.inside(batch, item["image"])
        old = project / "public/maps" / f"{old_name}.png"
        score = None
        if old_name not in known:
            category = "new"
        elif not old.exists():
            raise ValueError(f"旧地图库缺少图片：{old_name}")
        elif assets.same_pixels(source, old):
            category, score = "unchanged", 0.0
        else:
            score = assets.artwork_difference(source, old, manifest["config"])
            # This is a candidate classification; annotations record visual inspection.
            category = "preview_changed" if score > .04 else "ui_only"
        annotation = notes.get(name, {})
        category = annotation.get("category", category)
        if category not in LABELS:
            raise ValueError(f"未知分类：{category}")
        records.append({"name": name, "old_name": old_name if old_name in known else "",
                        "category": category, "artwork_difference": score,
                        "visually_reviewed": bool(annotation), "note": annotation.get("note", ""),
                        "source": Path(item["source"]).name, "row": item["row"], "col": item["col"],
                        "source_sha256": item["source_sha256"], "id": item["id"],
                        "new_source": source, "old_source": old if old_name in known else None})
    counts = Counter(i["category"] for i in records)
    covered = {i["old_name"] for i in records if i["old_name"]}
    missing = sorted(set(known) - covered)
    output.mkdir(parents=True)
    (output / "images").mkdir()
    order = {"preview_changed": 0, "ui_only": 1, "new": 2, "unchanged": 3}
    records.sort(key=lambda r: (order[r["category"]], -(r["artwork_difference"] or 0), r["name"]))
    for n, record in enumerate(records):
        record["new_image"] = f"images/{n:03d}-new.png"
        shutil.copy2(record.pop("new_source"), output / record["new_image"])
        old = record.pop("old_source")
        record["old_image"] = f"images/{n:03d}-old.png" if old else None
        if old:
            shutil.copy2(old, output / record["old_image"])
    report = {"summary": dict(counts), "current_maps": len(known), "confirmed_maps": len(records),
              "empty_positions": len(rows) - len(selected), "not_covered": missing,
              "renames": mapping, "items": records}
    assets.write_json(output / "report.json", report)
    fields = ["name", "old_name", "category", "artwork_difference", "visually_reviewed", "note", "source", "row", "col"]
    with (output / "map-changes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([{**r, "category": LABELS[r["category"]]} for r in records])
    template = Path(__file__).with_name("compare_template.html").read_text()
    payload = json.dumps(report, ensure_ascii=False).replace("<", "\\u003c")
    (output / "index.html").write_text(template.replace("__REPORT_DATA__", payload), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["summary", "current_maps", "confirmed_maps", "empty_positions", "not_covered"]}, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--project", type=Path, default=assets.PROJECT)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--renames", type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_report(args.batch.resolve(), args.project.resolve(), args.review, args.renames, args.output.resolve(), args.annotations)
