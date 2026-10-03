import { mapImage } from './mapTexture.js';

export function exportLayout(rows, cols) {
  if (![rows, cols].every(value => Number.isInteger(value) && value >= 1 && value <= 10)) {
    throw new Error('行列数必须在 1～10 之间');
  }
  const tileWidth = 281, tileHeight = 196, gap = 4, padding = 8;
  return {
    tileWidth, tileHeight, gap, padding,
    width: padding * 2 + cols * tileWidth + (cols - 1) * gap,
    height: padding * 2 + rows * tileHeight + (rows - 1) * gap,
  };
}

function loadImage(map, texture) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('无法加载地图图片：' + map.name));
    image.src = '/' + mapImage(map, texture).replace(/^\/+/, '');
  });
}

export async function exportPool(grid, rows, cols, texture = 'new') {
  const layout = exportLayout(rows, cols);
  if (!grid.length) throw new Error('请先添加地图');
  if (grid.length > rows * cols) throw new Error('地图数量超出当前布局，请先调整行列数或移除地图');
  // Source images are loaded before drawing; selection, theme, and viewport do not affect the PNG.
  const images = await Promise.all(grid.map(map => loadImage(map, texture)));
  const canvas = document.createElement('canvas');
  canvas.width = layout.width;
  canvas.height = layout.height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('浏览器无法创建图片画布');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  images.forEach((image, index) => {
    const x = layout.padding + (index % cols) * (layout.tileWidth + layout.gap);
    const y = layout.padding + Math.floor(index / cols) * (layout.tileHeight + layout.gap);
    context.drawImage(image, x, y, layout.tileWidth, layout.tileHeight);
  });
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('PNG 生成失败，请重试');
  return { blob, ...layout };
}
