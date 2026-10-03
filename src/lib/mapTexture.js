export function mapImage(map, texture = 'new') {
  return texture === 'old' && map.oldImg ? map.oldImg : map.img;
}

export function usesNewTextureFallback(map, texture) {
  return texture === 'old' && !map.oldImg;
}
