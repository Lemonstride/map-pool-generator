import React, { useEffect, useState } from 'react';
import { mapImage, usesNewTextureFallback } from '../lib/mapTexture';

export function MapCard({ map, texture = 'new' }) {
  const [failed, setFailed] = useState(false);
  const image = map ? mapImage(map, texture) : null;
  useEffect(() => setFailed(false), [image]);
  if (!map || failed) {
    return <div className="flex aspect-[281/196] items-center justify-center rounded bg-slate-100 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-300">
      {failed ? '图片加载失败' : '待添加地图'}
    </div>;
  }
  return <div><img src={'/' + image.replace(/^\/+/, '')} alt={map.name} width="281" height="196"
    loading="lazy" decoding="async" onError={() => setFailed(true)}
    className="aspect-[281/196] w-full rounded object-contain" />
    {usesNewTextureFallback(map, texture) && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">无旧贴图，使用新贴图</span>}
  </div>;
}
