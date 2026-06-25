import L from 'leaflet';

// Override default Leaflet icon paths which break under Vite bundling
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Create custom SVGs for beautiful pins
export const createDivIcon = (color: string, label: string) => {
  return L.divIcon({
    html: `
      <div class="flex flex-col items-center justify-center">
        <div class="flex items-center justify-center w-8 h-8 rounded-full shadow-lg border-2 border-white text-white font-bold" style="background-color: ${color};">
          ${label}
        </div>
        <div class="w-2 h-2 -mt-1 shadow-md rotate-45" style="background-color: ${color};"></div>
      </div>
    `,
    className: 'custom-leaflet-icon',
    iconSize: [32, 40],
    iconAnchor: [16, 40],
  });
};

export const driverIcon = createDivIcon('#22c55e', '🚴'); // green
export const shopIcon = createDivIcon('#a855f7', '🏪');   // purple
export const dropoffIcon = createDivIcon('#ef4444', '📍'); // red
