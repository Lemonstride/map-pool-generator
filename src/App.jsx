import React, { useEffect, useMemo, useState } from 'react';
import mapsData from './data/maps.json';
import { MapCard } from './components/MapCard';
import { MapSearchBar } from './components/MapSearchBar';
import { moveMap, restorePool, STORAGE_KEY } from './lib/pool';
import { exportPool } from './lib/exportPool';

function initialPool() {
  try { return restorePool(JSON.parse(localStorage.getItem(STORAGE_KEY)), mapsData); }
  catch { return restorePool(null, mapsData); }
}

export default function App() {
  const [initial] = useState(initialPool);
  const [rows, setRows] = useState(initial.rows);
  const [cols, setCols] = useState(initial.cols);
  const [texture, setTexture] = useState(initial.texture);
  const [grid, setGrid] = useState(initial.grid);
  const [selectedName, setSelectedName] = useState(null);
  const [theme, setTheme] = useState(() => initial.theme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  const [notice, setNotice] = useState(initial.missingCount ? '地图库已更新，已移除 ' + initial.missingCount + ' 张无法找到的地图。' : '');
  const [undoGrid, setUndoGrid] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(null);
  const capacity = rows * cols;
  const overflow = grid.length > capacity;
  const selectedIndex = grid.findIndex(map => map.name === selectedName);
  const selectedNames = useMemo(() => new Set(grid.map(map => map.name)), [grid]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ rows, cols, names: grid.map(map => map.name), theme, texture })); }
    catch { /* Editing also works when browser storage is unavailable. */ }
  }, [rows, cols, grid, theme, texture]);
  useEffect(() => () => { if (exported) URL.revokeObjectURL(exported.url); }, [exported]);

  function changeGrid(next) {
    setUndoGrid(grid); setGrid(next); setNotice(''); setExported(null);
  }
  function addMap(map) {
    if (exporting) return;
    if (selectedNames.has(map.name)) { setNotice('这张地图已经在图池里了。'); return; }
    if (grid.length >= capacity) { setNotice('图池已满，请增加行列数或移除地图。'); return; }
    changeGrid([...grid, map]);
  }
  function removeSelected() {
    if (selectedIndex < 0) return;
    changeGrid(grid.filter(map => map.name !== selectedName));
    setSelectedName(null); setNotice('已移除选中地图，可以撤销。');
  }
  function reorder(from, to) {
    if (exporting) return;
    if (from === to) return;
    const next = moveMap(grid, from, to);
    if (next !== grid) changeGrid(next);
  }
  async function download() {
    setExporting(true); setNotice('');
    try {
      const result = await exportPool(grid, rows, cols, texture);
      const url = URL.createObjectURL(result.blob);
      const filename = 'map_pool_' + texture + '.png';
      setExported({ url, width: result.width, height: result.height, filename, texture });
      const link = document.createElement('a');
      link.href = url; link.download = filename;
      document.body.append(link); link.click(); link.remove();
    } catch (error) { setNotice(error.message || '导出失败，请重试。'); }
    finally { setExporting(false); }
  }

  return <main className="min-h-screen bg-slate-50 p-4 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100 sm:p-6">
    <div className="mx-auto max-w-[1600px] space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold">图池生成器</h1><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">跑跑卡丁车 · ｜南山居客｜车队 西瓜卡</p></div>
        <button className="action" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? '☀️ 白天模式' : '🌙 夜间模式'}</button>
      </header>
      <section className="panel flex flex-wrap items-center gap-4" aria-label="图池布局">
        <label className="flex items-center gap-2 text-sm">行数
          <select aria-label="行数" disabled={exporting} value={rows} onChange={event => { setRows(Number(event.target.value)); setExported(null); }} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800">
            {Array.from({length:10}, (_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">列数
          <select aria-label="列数" disabled={exporting} value={cols} onChange={event => { setCols(Number(event.target.value)); setExported(null); }} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800">
            {Array.from({length:10}, (_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">地图贴图
          <select aria-label="地图贴图" disabled={exporting} value={texture} onChange={event => { setTexture(event.target.value); setExported(null); }} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800">
            <option value="new">新贴图</option><option value="old">旧贴图</option>
          </select>
        </label>
        <p className="text-sm text-slate-500 dark:text-slate-400">已选 {grid.length} / {capacity} 张 · 自动保存到此浏览器</p>
        <button onClick={download} disabled={!grid.length || overflow || exporting} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40 sm:ml-auto">
          {exporting ? '正在生成图片…' : '导出 PNG'}
        </button>
      </section>
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <MapSearchBar maps={mapsData} onSelect={addMap} selectedNames={selectedNames} texture={texture} disabled={exporting} />
        <section className="panel min-w-0" aria-labelledby="pool-title">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 id="pool-title" className="font-semibold">当前图池</h2>
            <span className="text-xs text-slate-500 dark:text-slate-400">点击选中 · 拖动调整顺序</span>
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            <button className="action" disabled={exporting || selectedIndex < 0} onClick={removeSelected}>移除选中</button>
            <button className="action" disabled={exporting || selectedIndex <= 0} onClick={() => reorder(selectedIndex, selectedIndex - 1)}>前移</button>
            <button className="action" disabled={exporting || selectedIndex < 0 || selectedIndex >= grid.length - 1} onClick={() => reorder(selectedIndex, selectedIndex + 1)}>后移</button>
            <button className="action" disabled={exporting || !grid.length} onClick={() => { changeGrid([]); setSelectedName(null); setNotice('已清空图池，可以撤销。'); }}>清空</button>
            <button className="action" disabled={exporting || !undoGrid} onClick={() => { setGrid(undoGrid); setUndoGrid(null); setSelectedName(null); setExported(null); setNotice('已撤销上一步操作。'); }}>撤销</button>
          </div>
          {overflow && <p role="alert" className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">当前布局最多容纳 {capacity} 张，已选 {grid.length} 张。所有地图仍保留；请调整布局或移除多余地图后再导出。</p>}
          <div className="overflow-x-auto p-1">
            <div className="grid gap-2" style={{gridTemplateColumns:'repeat(' + cols + ', minmax(112px, 1fr))'}}>
              {grid.map((map, index) => <button key={map.name} type="button" draggable
                aria-label={'选中 ' + map.name} aria-pressed={selectedName === map.name}
                onClick={() => setSelectedName(map.name)}
                onDragStart={event => event.dataTransfer.setData('text/plain', map.name)}
                onDragOver={event => event.preventDefault()}
                onDrop={event => { event.preventDefault(); reorder(grid.findIndex(item => item.name === event.dataTransfer.getData('text/plain')), index); }}
                className={'relative rounded-lg p-1 ' + (selectedName === map.name ? 'ring-2 ring-indigo-500' : 'hover:bg-slate-100 dark:hover:bg-slate-800')}>
                <MapCard map={map} texture={texture} />
                <span className="absolute left-2 top-2 rounded bg-slate-900/80 px-1.5 text-xs text-white" aria-hidden="true">{index+1}</span>
              </button>)}
              {Array.from({length:Math.max(0, capacity-grid.length)}, (_, index) => <div key={'empty-'+index} className="p-1"><MapCard /></div>)}
            </div>
          </div>
          <div role="status" aria-live="polite" className="mt-3 min-h-6 text-sm text-slate-600 dark:text-slate-300">{notice}</div>
          {exported && <div className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
            PNG 已生成：{exported.width} × {exported.height} · {exported.texture === 'old' ? '旧贴图' : '新贴图'}。
            <a className="ml-2 underline" href={exported.url} download={exported.filename}>重新下载</a>
            <details className="mt-2"><summary className="cursor-pointer">查看导出图片</summary><img className="mt-2 max-w-full" src={exported.url} alt="图池导出预览" /></details>
          </div>}
        </section>
      </div>
    </div>
  </main>;
}
