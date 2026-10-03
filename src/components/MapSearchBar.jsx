import React, { useMemo, useState } from 'react';
import Fuse from 'fuse.js';
import { MapCard } from './MapCard';

export function MapSearchBar({ maps, onSelect, selectedNames, texture, disabled = false }) {
  const [query, setQuery] = useState('');
  const [visibleCount, setVisibleCount] = useState(48);
  const fuse = useMemo(() => new Fuse(maps, {
    keys: [{ name: 'name', weight: 2 }, { name: 'pinyin', weight: 1 }, { name: 'aliases', weight: 0.5 }], threshold: 0.4,
  }), [maps]);
  const results = useMemo(() => query.trim()
    ? fuse.search(query.trim()).map(result => result.item)
    : maps, [query, fuse, maps]);

  return <section className="panel" aria-labelledby="library-title">
    <div className="mb-3 flex items-center justify-between">
      <h2 id="library-title" className="font-semibold">地图库</h2>
      <span className="text-xs text-slate-500 dark:text-slate-400">{results.length} 张地图</span>
    </div>
    <label htmlFor="map-search" className="sr-only">搜索地图</label>
    <input id="map-search" type="search" value={query}
      onChange={event => { setQuery(event.target.value); setVisibleCount(48); }}
      placeholder="搜索地图名称或拼音"
      className="mb-4 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white" />
    <div className="max-h-[420px] overflow-y-auto p-1">
      {!results.length && <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">没有找到匹配的地图</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
        {results.slice(0, visibleCount).map(map => {
          const selected = selectedNames.has(map.name);
          return <button key={map.name} type="button" disabled={disabled} onClick={() => onSelect(map)}
            aria-label={(selected ? '已添加 ' : '添加 ') + map.name} aria-pressed={selected}
            className={'rounded-lg p-1 text-left transition hover:bg-slate-100 dark:hover:bg-slate-800 ' + (selected ? 'ring-2 ring-indigo-500' : '')}>
            <MapCard map={map} texture={texture} />
            <span className="mt-1 block truncate text-xs text-slate-600 dark:text-slate-300">{map.name}{selected ? ' · 已添加' : ''}</span>
          </button>;
        })}
      </div>
      {results.length > visibleCount && <button className="action mt-4 w-full" onClick={() => setVisibleCount(count => count + 48)}>显示更多地图</button>}
    </div>
  </section>;
}
