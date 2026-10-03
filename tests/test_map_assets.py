import argparse
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from tools import map_assets as assets


class MapAssetsTests(unittest.TestCase):
    def setUp(self):
        scratch = assets.PROJECT / "work/tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        (self.project / "src/data").mkdir(parents=True)
        (self.project / "public/maps").mkdir(parents=True)
        self.catalog = [{"name": "已有地图", "img": "maps/已有地图.png", "pinyin": "keep-original-pinyin"}]
        for p in ["src/data/maps.json", "maps.json"]:
            assets.write_json(self.project / p, self.catalog)
        Image.new("RGB", (20, 15), "black").save(self.project / "public/maps/已有地图.png")
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.screenshot = self.inputs / "screen.png"
        image = Image.new("RGB", (100, 80), "white")
        image.paste("red", (4, 5, 24, 20))
        image.paste("blue", (27, 5, 47, 20))
        image.save(self.screenshot)
        self.config = {
            "reference_size": [100, 80], "start": [4, 5], "tile_size": [20, 15],
            "gap": [3, 2], "rows": 2, "cols": 2, "name_top_ratio": 0.8,
            "confidence_threshold": 0.92, "model_name": "PP-OCRv5_server_rec"
        }
        self.config_file = self.root / "config.json"
        assets.write_json(self.config_file, self.config)
        self.batch = self.root / "batch"

    def prepare(self, inputs=None, scale=False):
        return assets.prepare(argparse.Namespace(
            project=self.project, output=self.batch, config=self.config_file,
            inputs=inputs or [str(self.screenshot)], scale=scale, skip_ocr=True
        ))

    def approve(self, names):
        manifest = assets.load_manifest(self.batch)
        rows = assets.review_rows(manifest)
        for row, name in zip(rows, names):
            row["name"], row["approved"] = name, "true"
        self.write_rows(rows)

    def write_rows(self, rows):
        with (self.batch / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=assets.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_crops_preserve_pixels_and_report_empty_files(self):
        (self.inputs / "empty.png").touch()
        manifest = self.prepare([str(self.inputs), str(self.screenshot)])
        self.assertEqual(len(manifest["items"]), 4)
        self.assertEqual(len(manifest["skipped"]), 1)
        with Image.open(self.batch / manifest["items"][0]["image"]) as first:
            self.assertEqual(first.size, (20, 15))
            self.assertEqual(first.getpixel((19, 14)), (255, 0, 0))
        with Image.open(self.batch / manifest["items"][1]["image"]) as second:
            self.assertEqual(second.getpixel((0, 0)), (0, 0, 255))
        self.assertTrue((self.batch / "review.html").exists())

    def test_resolution_mismatch_creates_no_output(self):
        Image.new("RGB", (200, 160)).save(self.screenshot)
        with self.assertRaisesRegex(ValueError, "截图尺寸"):
            self.prepare()
        self.assertFalse(self.batch.exists())

    def test_empty_name_frame_does_not_become_ocr_text(self):
        card = Image.new("RGB", (281, 196), (229, 231, 236))
        draw = ImageDraw.Draw(card)
        draw.rectangle((0, 0, 280, 195), outline="black", width=2)
        config = {**self.config, "tile_size": [281, 196], "name_top_ratio": 0.84}
        self.assertIsNone(assets.extract_name_strip(card, config))

    def test_explicit_proportional_scaling_preserves_crop_size(self):
        with Image.open(self.screenshot) as image:
            image.resize((200, 160), Image.Resampling.NEAREST).save(self.inputs / "large.png")
        manifest = self.prepare([str(self.inputs / "large.png")], scale=True)
        with Image.open(self.batch / manifest["items"][0]["image"]) as card:
            self.assertEqual(card.size, (40, 30))
            self.assertEqual(card.getpixel((0, 0)), (255, 0, 0))

    def test_collision_rejects_entire_batch_before_writes(self):
        self.prepare()
        self.approve(["新地图", "已有地图"])
        original = (self.project / "src/data/maps.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "已有不同图片"):
            assets.sync_batch(self.batch, self.project)
        self.assertFalse((self.project / "public/maps/新地图.png").exists())
        self.assertEqual((self.project / "src/data/maps.json").read_bytes(), original)
        self.assertFalse((self.project / "work").exists())

    def test_approved_duplicate_names_cannot_overwrite_each_other(self):
        self.prepare()
        self.approve(["新地图", "新地图"])
        with self.assertRaisesRegex(ValueError, "名称重复"):
            assets.sync_batch(self.batch, self.project)
        self.assertFalse((self.project / "public/maps/新地图.png").exists())

    def test_preview_then_sync_keeps_existing_pinyin_and_backs_up(self):
        self.prepare()
        self.approve(["新地图", "已有地图"])
        preview = assets.sync_batch(self.batch, self.project, replace_existing=True, dry_run=True)
        self.assertEqual(preview["map_count"], 2)
        self.assertFalse((self.project / "work").exists())
        result = assets.sync_batch(self.batch, self.project, replace_existing=True)
        self.assertEqual(assets.read_json(self.project / "src/data/maps.json"),
                         assets.read_json(self.project / "maps.json"))
        catalog = assets.read_json(self.project / "src/data/maps.json")
        self.assertEqual(catalog[0]["pinyin"], "keep-original-pinyin")
        self.assertEqual(catalog[1]["pinyin"], "xinditu")
        with Image.open(Path(result["backup"]) / "public/maps/已有地图.png") as image:
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))

    def test_modified_crop_is_rejected(self):
        manifest = self.prepare()
        self.approve(["新地图"])
        Image.new("RGB", (20, 15), "green").save(self.batch / manifest["items"][0]["image"])
        with self.assertRaisesRegex(ValueError, "被修改"):
            assets.sync_batch(self.batch, self.project)
        self.assertFalse((self.project / "public/maps/新地图.png").exists())

    def test_rename_preserves_catalog_position_alias_and_old_image_backup(self):
        self.prepare()
        self.approve(["正确地图名"])
        renames = self.root / "renames.json"
        assets.write_json(renames, {"已有地图": "正确地图名"})
        preview = assets.sync_batch(self.batch, self.project, renames=renames, dry_run=True)
        self.assertEqual(preview["map_count"], 1)
        self.assertTrue((self.project / "public/maps/已有地图.png").exists())
        result = assets.sync_batch(self.batch, self.project, renames=renames)
        catalog = assets.read_json(self.project / "src/data/maps.json")
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["name"], "正确地图名")
        self.assertEqual(catalog[0]["aliases"], ["已有地图"])
        self.assertEqual(catalog[0]["pinyin"], "zhengquedituming")
        self.assertFalse((self.project / "public/maps/已有地图.png").exists())
        self.assertTrue((Path(result["backup"]) / "public/maps/已有地图.png").exists())

    def test_rename_requires_approved_destination(self):
        self.prepare()
        self.approve(["其他地图"])
        renames = self.root / "renames.json"
        assets.write_json(renames, {"已有地图": "正确地图名"})
        with self.assertRaisesRegex(ValueError, "已确认"):
            assets.sync_batch(self.batch, self.project, renames=renames)
        self.assertTrue((self.project / "public/maps/已有地图.png").exists())

    def test_rename_failure_restores_old_and_new_files(self):
        self.prepare()
        self.approve(["正确地图名"])
        renames = self.root / "renames.json"
        assets.write_json(renames, {"已有地图": "正确地图名"})
        original = (self.project / "src/data/maps.json").read_bytes()
        real_unlink = Path.unlink
        old_image = self.project / "public/maps/已有地图.png"

        def fail_old_unlink(path, *args, **kwargs):
            if path == old_image:
                raise OSError("Simulated retirement failure")
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail_old_unlink):
            with self.assertRaisesRegex(OSError, "retirement failure"):
                assets.sync_batch(self.batch, self.project, renames=renames)
        self.assertTrue(old_image.exists())
        self.assertFalse((self.project / "public/maps/正确地图名.png").exists())
        self.assertEqual((self.project / "src/data/maps.json").read_bytes(), original)
        self.assertEqual((self.project / "maps.json").read_bytes(), original)

    def test_keep_legacy_preserves_original_pixels_across_later_updates(self):
        self.prepare()
        self.approve(["新地图", "已有地图"])
        assets.sync_batch(self.batch, self.project, replace_existing=True, keep_legacy=True)
        catalog = assets.read_json(self.project / "src/data/maps.json")
        self.assertEqual(catalog[0]["oldImg"], "maps-legacy/已有地图.png")
        self.assertIsNone(catalog[1]["oldImg"])
        legacy = self.project / "public" / catalog[0]["oldImg"]
        original = legacy.read_bytes()
        with Image.open(legacy) as image:
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
        assets.sync_batch(self.batch, self.project, replace_existing=True, keep_legacy=True)
        self.assertEqual(legacy.read_bytes(), original)
        self.assertIsNone(assets.read_json(self.project / "src/data/maps.json")[1]["oldImg"])

    def test_legacy_copy_is_removed_if_atomic_write_fails(self):
        self.prepare()
        self.approve(["已有地图"])
        original = (self.project / "src/data/maps.json").read_bytes()
        real_replace = assets.os.replace
        calls = 0

        def fail_after_legacy_copy(source, target):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("Simulated legacy write failure")
            return real_replace(source, target)

        with patch.object(assets.os, "replace", side_effect=fail_after_legacy_copy):
            with self.assertRaisesRegex(OSError, "legacy write failure"):
                assets.sync_batch(self.batch, self.project, replace_existing=True, keep_legacy=True)
        self.assertFalse((self.project / "public/maps-legacy/已有地图.png").exists())
        self.assertEqual((self.project / "src/data/maps.json").read_bytes(), original)
        with Image.open(self.project / "public/maps/已有地图.png") as image:
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))

    def test_rename_identical_image_reuses_corrected_filename_for_legacy(self):
        manifest = self.prepare()
        self.approve(["正确地图名"])
        shutil_source = self.batch / manifest["items"][0]["image"]
        (self.project / "public/maps/已有地图.png").write_bytes(shutil_source.read_bytes())
        renames = self.root / "renames.json"
        assets.write_json(renames, {"已有地图": "正确地图名"})
        result = assets.sync_batch(self.batch, self.project, renames=renames, keep_legacy=True)
        self.assertEqual(result["legacy_copies"], 0)
        item = assets.read_json(self.project / "src/data/maps.json")[0]
        self.assertEqual(item["oldImg"], item["img"])
        self.assertTrue((self.project / "public" / item["oldImg"]).exists())

    def test_unknown_csv_id_is_rejected(self):
        manifest = self.prepare()
        rows = assets.review_rows(manifest)
        rows[0]["id"] = "wrong-batch"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "完整对应"):
            assets.sync_batch(self.batch, self.project)

    def test_path_in_map_name_is_rejected(self):
        self.prepare()
        self.approve(["../新地图"])
        with self.assertRaisesRegex(ValueError, "禁用字符"):
            assets.sync_batch(self.batch, self.project)

    def test_unreviewed_batch_is_not_synced(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "没有确认"):
            assets.sync_batch(self.batch, self.project)

    def test_compare_reports_new_and_changed_without_writing(self):
        self.prepare()
        self.approve(["新地图", "已有地图"])
        before = (self.project / "src/data/maps.json").read_bytes()
        result = assets.compare_batch(self.batch, self.project)
        self.assertEqual(result["summary"]["new_name"], 1)
        self.assertEqual(result["summary"]["image_changed"], 1)
        self.assertEqual(result["summary"]["unrecognized"], 2)
        self.assertEqual(result["not_covered"], [])
        self.assertEqual((self.project / "src/data/maps.json").read_bytes(), before)
        self.assertFalse((self.project / "public/maps/新地图.png").exists())

    def test_partial_batch_does_not_remove_uncovered_maps(self):
        self.prepare()
        result = assets.compare_batch(self.batch, self.project)
        self.assertEqual(result["not_covered"], ["已有地图"])
        self.assertTrue((self.project / "public/maps/已有地图.png").exists())

    def test_ocr_retry_does_not_destroy_manual_corrections(self):
        self.prepare()
        self.approve(["人工校正名称"])
        with self.assertRaisesRegex(ValueError, "核对表已"):
            assets.recognize(self.batch, self.project)

    def test_failed_write_restores_images_and_catalog(self):
        self.prepare()
        self.approve(["新地图", "已有地图"])
        original = (self.project / "src/data/maps.json").read_bytes()
        real_replace = assets.os.replace
        calls = 0

        def fail_third_write(source, target):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("Simulated disk failure")
            return real_replace(source, target)

        with patch.object(assets.os, "replace", side_effect=fail_third_write):
            with self.assertRaisesRegex(OSError, "disk failure"):
                assets.sync_batch(self.batch, self.project, replace_existing=True)
        self.assertFalse((self.project / "public/maps/新地图.png").exists())
        with Image.open(self.project / "public/maps/已有地图.png") as image:
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual((self.project / "src/data/maps.json").read_bytes(), original)
        self.assertEqual((self.project / "maps.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
