# 游戏截图处理

所有命令从网站仓库根目录执行。原始工具和输入仍保存在本地 preProcessMap/；新工具在 tools/，不会依赖另一台电脑的 Windows 路径。

## Conda 环境

    conda env create --prefix ./.conda --file environment.yml
    conda activate ./.conda

当前 Mac 已创建这个环境。VS Code 打开仓库根目录即可使用配置中的 .conda/bin/python；也可以在“Python: Select Interpreter”中选择它。

首次识别会从 Paddle 官方 BOS 下载模型，缓存位于项目 .cache/。图片在本机推理，不上传到 OCR 服务。固定的直接依赖见 requirements.txt；完整的已验证 Mac ARM 依赖见 requirements-lock-osx-arm64.txt。

## 1. 生成待核对批次

    python tools/map_assets.py prepare preProcessMap/originalMap/d.png --output work/maps/demo

可以传多个截图文件，也可以传整个目录。目录扫描只处理这一层的 PNG/JPG/JPEG，空文件与损坏文件会记录为跳过项。每张原图裁成 3 行 × 4 列卡片，并识别底部名称。

输出：

- tiles/：使用来源 ID 命名的卡片，OCR 重名也不会覆盖。
- manifest.json：截图来源、图片校验值、OCR 结果、置信度和需要检查的项目。
- review.html：可直接在浏览器打开的本地核对页。
- review.csv：可在 VS Code 或表格工具中编辑的核对表。

同名批次不能覆盖，请使用新目录。若只想先裁切或下载模型时失败：

    python tools/map_assets.py prepare preProcessMap/originalMap/d.png --output work/maps/crops --skip-ocr
    python tools/map_assets.py ocr work/maps/crops

已有人工修改的核对表不会被后一次 OCR 覆盖。

## 2. 核对名称

打开 review.html，逐张修改名称并勾选“图片与名称已确认”，然后下载 review.csv。可以通过核对页上的“继续已有核对”导入已保存 CSV。页面刷新会重置尚未下载的修改。

若浏览器没有保存下载文件，展开“下载不成功时：复制核对表文本”，将生成的完整文本保存为 UTF-8 编码的 CSV，再通过 --review 指定它。

也可以直接编辑原始 review.csv：修改 name，将确认项的 approved 改成 true。低置信度、未知名称和重复项都需要核对；候选名称只是参考，不会自动替换 OCR 原文或自动确认。新地图无需出现在现有地图库中。

## 3. 全量截图与旧地图库对比

    python tools/map_assets.py compare work/maps/demo --output work/maps/demo/comparison.json

报告列出新名称、同名图片变化、相同图片、空卡片、重复名称和旧库中没有被这批截图覆盖的地图。人工改名后可以传入 --review 再次对比。

新名称也可能是 OCR 错字；同名图片变化可能来自贴图更新、界面元素或裁切差异。artwork_difference 是排除难度栏和名称栏后的画面差异，0 表示相同，越大表示差异越明显。它用于辅助核对，不自动认定贴图更新。

全量更新时先解决重复、空卡片和名称问题，再核对未覆盖的旧地图。未覆盖条目不会自动删除，避免漏截一页就丢失地图。

需要可搜索的新旧图片对照页时，在同步前运行：

    python tools/map_compare_report.py work/maps/demo --review work/maps/demo/reviewed.csv --output outputs/map-comparison

报告包含独立保存的新旧图片、HTML 对照页、JSON 和 CSV 清单，后续同步不会改变报告中的旧图片。默认差异分类是辅助结果，需要逐图核对；可使用 --annotations 传入名称到 category/note 的 JSON 核对记录。category 支持 preview_changed、ui_only、unchanged、new。--renames 可指定历史错字的旧名称到新名称映射。

截图尽量保持相同窗口尺寸、界面缩放和地图排序。连续翻页时可以保留一行重叠以防漏图；重复卡片只确认其中一份。所有旧图也重新截图，才能检查同名地图的贴图更新。

## 4. 同步到网站

先检查待执行的变更。如果下载的 CSV 在其他位置，使用 --review /path/to/review.csv。

    python tools/map_assets.py sync work/maps/demo --dry-run
    python tools/map_assets.py sync work/maps/demo

只同步 approved=true 的项。新图片写入 public/maps/，地图数据同时更新 src/data/maps.json 和仓库根目录 maps.json，新增项自动生成拼音。现有地图的拼音保留。

如果同名图片的像素完全相同，会跳过图片写入；不同图片会拒绝整批写入，确认替换时显式加 --replace-existing。写入前备份受影响的图片与 JSON 到 work/backups/，发生写入错误时自动恢复。

同步只修改本地仓库，随后可以检查 Git diff。提交或部署网站按正常开发流程进行。

### 保留新旧贴图

    python tools/map_assets.py sync work/maps/demo --review work/maps/demo/reviewed.csv --replace-existing --keep-legacy --dry-run
    python tools/map_assets.py sync work/maps/demo --review work/maps/demo/reviewed.csv --replace-existing --keep-legacy

--keep-legacy 为原有地图保存 oldImg 路径。不同的旧图片保存在 public/maps-legacy/；像素相同的图片复用当前文件。新增地图记录 oldImg=null，旧贴图模式会显示说明并使用新图片。后续同步保留已经保存的旧版本。

### 修正历史名称

旧数据有错字或截断时，提供旧名称到正确名称的 JSON 对象，并使用 --renames /path/to/renames.json。正确名称必须出现在已确认核对表中，且不能与现有名称冲突。

工具会保留地图原有顺序，更新图片路径与拼音，将旧名称写入 aliases，并在备份后清理旧文件名。网页通过别名恢复之前保存的图池。名称、图片、新旧版本和 JSON 在同一次同步中写入，失败时恢复备份。

## 不同截图尺寸

默认 map_assets_config.json 对应原脚本的 1922 × 1113 窗口截图，卡片起点 (480, 273)，大小 281 × 196，间距 10。

等比例缩放的截图可加 --scale；窗口位置、卡片排布或 UI 缩放方式改变时，复制配置并调整坐标、尺寸与间距，再用 --config 指定。工具拒绝不匹配的尺寸和越界裁切。OCR 名称区域默认使用卡片底部 16%，可用 name_top_ratio 调整。

## 验证

    python -m unittest discover -s tests -v

测试覆盖裁切像素、空输入、截图缩放、重名覆盖、核对表错误、篡改图片、差异报告、同步预览、备份和写入失败恢复。

环境、缓存、原始截图、历史 ZIP 和生成批次均已从 Git 与 Vercel 上传内容中排除。
