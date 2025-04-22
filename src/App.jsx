// App.jsx
import React, { useState } from 'react';
import mapsData from './data/maps.json';
import { MapCard } from './components/MapCard';
import { MapSearchBar } from './components/MapSearchBar';
import html2canvas from 'html2canvas';

export default function App() {
    const [cols] = useState(5);
    const [grid, setGrid] = useState([]);
    const [selectedIndex, setSelectedIndex] = useState(null);
    const [maxGridSize, setMaxGridSize] = useState(15);
    const [isDark, setIsDark] = useState(false);

    const handleSelectMap = (map) => {
        if (grid.length >= maxGridSize) {
            alert(`图池已满，最多只能添加 ${maxGridSize} 张地图`);
            return;
        }
        const isDuplicate = grid.some(item => item.name === map.name);
        if (isDuplicate) {
            alert(`地图 "${map.name}" 已经添加过啦！`);
            return;
        }
        setGrid([...grid, map]);
    };

    const handleClearGrid = () => {
        setGrid([]);
        setSelectedIndex(null);
    };

    const handleDeleteSelected = () => {
        if (selectedIndex !== null && selectedIndex < grid.length) {
            const updated = [...grid];
            updated.splice(selectedIndex, 1);
            setGrid(updated);
            setSelectedIndex(null);
        }
    };

    const exportImage = () => {
        html2canvas(document.querySelector("#grid"), {
            scale: 2,
            useCORS: true
        }).then(canvas => {
            const link = document.createElement("a");
            link.download = "map_pool.png";
            link.href = canvas.toDataURL("image/png");
            link.click();
        });
    };

    return (
        <div className={`p-4 space-y-4 min-h-screen transition-colors duration-300 ${isDark ? 'dark bg-gray-900 text-white' : 'bg-white text-black'}`}>
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold">图池生成器</h1>
                <div className="flex items-center gap-4">
    <span className="text-sm text-gray-500 dark:text-gray-400 hidden sm:inline">
      -｜南山居客｜车队 西瓜卡 开发
    </span>
                    <button
                        onClick={() => setIsDark(!isDark)}
                        className="bg-indigo-500 text-white px-3 py-1 rounded"
                    >
                        {isDark ? '☀️ 白天模式' : '🌙 夜间模式'}
                    </button>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <label>图池上限：</label>
                <input
                    type="number"
                    value={maxGridSize}
                    onChange={(e) => setMaxGridSize(Number(e.target.value))}
                    min={1}
                    className={`border px-2 py-1 w-24 rounded outline-none ${isDark ? 'bg-gray-800 text-white border-gray-600' : 'bg-white text-black'}`}
                />
            </div>

            <MapSearchBar maps={mapsData} onSelect={handleSelectMap} />

            <div className="flex gap-2 flex-wrap">
                <button onClick={handleDeleteSelected} className="bg-red-500 text-white px-3 py-1 rounded hover:opacity-90">删除选中项</button>
                <button onClick={handleClearGrid} className="bg-gray-400 text-white px-3 py-1 rounded hover:opacity-90">清空图池</button>
                <button onClick={exportImage} className="bg-green-500 text-white px-3 py-1 rounded ml-auto hover:opacity-90">导出为图片</button>
            </div>

            <div
                id="grid"
                className="grid gap-1 p-2 rounded bg-white dark:bg-gray-800 transition-all"
                style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
            >
                {grid.map((map, i) => (
                    <div
                        key={i}
                        onClick={() => setSelectedIndex(i)}
                        className={`relative cursor-pointer rounded overflow-hidden transition-all duration-200 ${
                            selectedIndex === i
                                ? 'ring-4 ring-blue-400 shadow-md after:absolute after:inset-0 after:bg-white/40 dark:after:bg-black/40 after:backdrop-blur-sm'
                                : 'hover:ring-2 hover:ring-blue-200'
                        }`}
                    >
                        <MapCard map={map} />
                    </div>
                ))}
            </div>
        </div>
    );
}
