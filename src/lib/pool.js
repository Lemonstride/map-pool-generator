export const STORAGE_KEY = 'map-pool-generator:v1';

export function dimension(value, fallback) {
  return typeof value === 'number' && Number.isInteger(value)
    ? Math.min(10, Math.max(1, value))
    : fallback;
}

export function restorePool(saved, maps) {
  const state = saved && typeof saved === 'object' ? saved : {};
  const byName = new Map(maps.map(map => [map.name, map]));
  for (const map of maps) {
    for (const alias of map.aliases || []) {
      if (!byName.has(alias)) byName.set(alias, map);
    }
  }
  const names = Array.isArray(state.names) ? [...new Set(state.names)] : [];
  return {
    rows: dimension(state.rows, 3),
    cols: dimension(state.cols, 5),
    grid: [...new Set(names.filter(name => byName.has(name)).map(name => byName.get(name)))],
    missingCount: names.filter(name => typeof name === 'string' && !byName.has(name)).length,
    theme: ['light', 'dark'].includes(state.theme) ? state.theme : null,
    texture: state.texture === 'old' ? 'old' : 'new',
  };
}

export function moveMap(grid, from, to) {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from >= grid.length || to >= grid.length) return grid;
  const next = [...grid];
  const [map] = next.splice(from, 1);
  next.splice(to, 0, map);
  return next;
}
