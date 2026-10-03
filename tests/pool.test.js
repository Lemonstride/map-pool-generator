import test from 'node:test';
import assert from 'node:assert/strict';
import { moveMap, restorePool } from '../src/lib/pool.js';
import { exportLayout, exportPool } from '../src/lib/exportPool.js';
import { mapImage, usesNewTextureFallback } from '../src/lib/mapTexture.js';

const maps = [{name:'A',img:'maps/A.png'}, {name:'B',img:'maps/B.png'}];

test('saved pool restores current map data and removes missing/duplicate names', () => {
  const restored = restorePool({rows:0,cols:20,names:['B','B','removed','A'],theme:'dark'}, maps);
  assert.deepEqual(restored.grid, [maps[1],maps[0]]);
  assert.equal(restored.missingCount, 1);
  assert.equal(restored.rows, 1);
  assert.equal(restored.cols, 10);
});

test('shrinking layout keeps every selected map available', () => {
  assert.equal(restorePool({rows:1,cols:1,names:['A','B']}, maps).grid.length, 2);
});

test('renamed maps restore from old names without duplicating current names', () => {
  const renamed = [{name:'正确名称',img:'maps/正确名称.png',aliases:['旧错字']}];
  const restored = restorePool({names:['旧错字','正确名称']}, renamed);
  assert.deepEqual(restored.grid, renamed);
  assert.equal(restored.missingCount, 0);
});

test('texture selection restores safely and uses new artwork when no old artwork exists', () => {
  assert.equal(restorePool({texture:'old'}, maps).texture, 'old');
  assert.equal(restorePool({texture:'invalid'}, maps).texture, 'new');
  const changed = {name:'A',img:'maps/A.png',oldImg:'maps-legacy/A.png'};
  assert.equal(mapImage(changed, 'old'), 'maps-legacy/A.png');
  assert.equal(mapImage(changed, 'new'), 'maps/A.png');
  assert.equal(mapImage(maps[1], 'old'), 'maps/B.png');
  assert.equal(usesNewTextureFallback(maps[1], 'old'), true);
  assert.equal(usesNewTextureFallback(changed, 'old'), false);
});

test('invalid saved dimensions fall back to valid values', () => {
  const state = restorePool({rows:1.5,cols:'0'}, maps);
  assert.equal(state.rows, 3);
  assert.equal(state.cols, 5);
});

test('reordering leaves source data intact', () => {
  assert.deepEqual(moveMap(maps,0,1), [maps[1],maps[0]]);
  assert.deepEqual(maps.map(map=>map.name), ['A','B']);
  assert.equal(moveMap(maps,-1,1), maps);
});

test('export dimensions are independent of the browser viewport', () => {
  assert.deepEqual(exportLayout(1,2), {tileWidth:281,tileHeight:196,gap:4,padding:8,width:582,height:212});
  assert.throws(()=>exportLayout(0,5));
});

test('empty and overflowing pools never start image loading', async () => {
  await assert.rejects(exportPool([],1,1), /先添加/);
  await assert.rejects(exportPool(maps,1,1), /超出/);
});
