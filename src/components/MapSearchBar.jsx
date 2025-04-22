// src/components/MapSearchBar.jsx
import React, { useState } from 'react';
import Fuse from 'fuse.js';

export function MapSearchBar({ maps, onSelect }) {
    const [query, setQuery] = useState('');

    const fuse = new Fuse(maps, {
        keys: ['name', 'pinyin'],
        threshold: 0.4
    });

    const results = query ? fuse.search(query).map(r => r.item) : [];

    return (
        <div className="mb-4">
            <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索地图（支持拼音）"
                className="p-1 text-sm border w-full rounded-md max-w-xl mx-auto mb-2 outline-none bg-white text-black dark:bg-gray-800 dark:text-white dark:border-gray-600"
            />
            {results.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-1">
                    {results.map((map, idx) => (
                        <div
                            key={idx}
                            onClick={() => onSelect(map)}
                            className="cursor-pointer hover:opacity-80 transition-all"
                        >
                            <div className="aspect-[4/3] overflow-hidden">
                                <img
                                    src={map.img}
                                    alt={map.name}
                                    className="w-full h-full object-cover"
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}