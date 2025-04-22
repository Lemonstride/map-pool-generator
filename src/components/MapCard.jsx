// src/components/MapCard.jsx
import React from 'react';

export function MapCard({ map }) {
    if (!map) {
        return (
            <div className="aspect-[4/3] bg-gray-100 dark:bg-gray-700 border border-dashed" />
        );
    }

    return (
        <div className="overflow-hidden aspect-[4/3]">
            <img
                src={map.img}
                alt=""
                className="w-full h-full object-cover"
            />
        </div>
    );
}