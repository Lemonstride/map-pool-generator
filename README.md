# Map Pool Generator

《跑跑卡丁车》赛事图池生成器。搜索地图、编排图池，并导出可直接分享的 PNG 图片。

**在线使用：[mappoolgenerator.online](https://www.mappoolgenerator.online/)**

由「｜南山居客｜」车队西瓜卡开发。

## 功能

- **地图搜索**：支持中文名称、拼音和模糊匹配，也兼容修正前的旧名称。
- **图池编排**：行列数各支持 1–10；可拖动排序、前后移动、移除、清空和撤销。缩小布局会保留已选地图，超出容量时提示调整。
- **新旧贴图切换**：地图库、当前图池和 PNG 导出使用同一套贴图。新地图没有旧贴图时，会注明并使用新贴图。
- **PNG 导出**：按每张卡片 281 × 196 像素生成图片，预览、昼夜模式和窗口尺寸不会影响导出结果。
- **自动保存**：在同一浏览器中保存地图、顺序、布局、贴图版本和昼夜模式。
- **移动端使用**：小屏幕布局、点击选中及按钮排序。

自动保存使用浏览器本地存储；更换浏览器或清除站点数据后，需要重新建立图池。

## 使用

1. 设置图池的行数、列数和贴图版本。
2. 搜索地图，点击卡片加入图池。
3. 在图池中选中地图，通过拖动或「前移／后移」调整顺序。
4. 点击「导出 PNG」。生成后可查看图片或重新下载。

旧贴图来自更新前的网站地图库。新增地图不具备历史图片；切换版本不会改变已选地图或顺序。

## 地图库

2026-10-03 使用 29 张游戏截图完成全量更新：

| 项目 | 数量 |
| --- | ---: |
| 当前地图 | 339 |
| 新增地图 | 10 |
| 原有地图预览发生变化 | 100 |
| 仅界面标记发生变化 | 22 |
| 新旧图片像素相同 | 207 |
| 修正的历史名称 | 6 |

原有 329 张地图均保留旧贴图。这里的预览变化包括场景画面、视角、色彩和路线图渲染变化；不等同于确认游戏内部的贴图资源更换。

## 本地开发

前端使用 React、Vite、Tailwind CSS 和 Fuse.js。

```bash
npm ci
npm run dev
```

开发地址以终端输出为准，通常是 `http://localhost:5173/`。

```bash
npm test          # 图池恢复、排序、贴图选择及导出边界验证
npm run build    # 生成 dist/
npm run preview  # 预览构建结果
```

Vercel 项目使用 Vite，构建命令为 `npm run build`，输出目录为 `dist`。网站运行不需要 Python 或 Conda。

## 游戏截图更新

截图处理在本机完成，使用独立 Conda 环境。流程为：

**裁切与 OCR → 核对名称 → 新旧图片对比 → 同步预览 → 备份并写入**

```bash
conda env create --prefix ./.conda --file environment.yml
conda activate ./.conda
python tools/map_assets.py prepare /path/to/screenshots --output work/maps/batch-name
```

详细命令、核对页面、旧贴图保留与名称修正方法见 [截图处理说明](tools/README.md)。原图、环境、模型缓存和临时输出不提交到 Git，也不上传到 Vercel。

## 项目结构

```text
public/maps/          当前地图图片
public/maps-legacy/   与当前版本不同的旧图片
src/data/maps.json    地图库与新旧图片路径
src/components/      地图卡片与搜索界面
src/lib/             图池恢复、贴图选择与 PNG 导出
tools/               截图处理和对比报告工具
tests/               前端逻辑及处理流程验证
environment.yml      Conda 环境定义
```

仓库根目录的 `maps.json` 保留为兼容数据，由同步工具与 `src/data/maps.json` 一起更新。

## 许可

MIT。
