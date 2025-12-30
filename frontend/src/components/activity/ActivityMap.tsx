import { useMemo } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import type { ActivitySample } from '../../types/api';

const MAPBOX_TOKEN = 'pk.eyJ1Ijoia25lY2h0MDEwMiIsImEiOiJjbWpyZXlubGI0ZnZwM2NxM3pkaWFya3QzIn0.mLS4t_0PeqoqN4rI9pOnqA';

interface ActivityMapProps {
  samples: ActivitySample[];
  className?: string;
}

// Route line style
const routeLayerStyle: LayerProps = {
  id: 'route',
  type: 'line',
  paint: {
    'line-color': '#00d4ff',
    'line-width': 4,
    'line-opacity': 0.9,
  },
};

export function ActivityMap({ samples, className = '' }: ActivityMapProps) {
  // Filter samples with valid GPS coordinates
  const gpsPoints = useMemo(() => {
    return samples
      .filter((s) => s.latitude != null && s.longitude != null)
      .map((s) => ({
        lat: s.latitude!,
        lng: s.longitude!,
      }));
  }, [samples]);

  // Calculate center
  const center = useMemo(() => {
    if (gpsPoints.length < 2) {
      return { lat: 37.5665, lng: 126.978 }; // Seoul default
    }

    const lats = gpsPoints.map((p) => p.lat);
    const lngs = gpsPoints.map((p) => p.lng);

    return {
      lat: (Math.min(...lats) + Math.max(...lats)) / 2,
      lng: (Math.min(...lngs) + Math.max(...lngs)) / 2,
    };
  }, [gpsPoints]);

  // GeoJSON for the route line
  const routeGeoJSON = useMemo(() => {
    return {
      type: 'Feature' as const,
      properties: {},
      geometry: {
        type: 'LineString' as const,
        coordinates: gpsPoints.map((p) => [p.lng, p.lat]),
      },
    };
  }, [gpsPoints]);

  if (gpsPoints.length < 2) {
    return (
      <div className={`card p-4 text-center ${className}`}>
        <p className="text-muted text-sm">GPS 데이터가 없습니다</p>
      </div>
    );
  }

  const startPoint = gpsPoints[0];
  const endPoint = gpsPoints[gpsPoints.length - 1];

  return (
    <div className={`card overflow-hidden h-full ${className}`}>
      <Map
        initialViewState={{
          latitude: center.lat,
          longitude: center.lng,
          zoom: 13,
        }}
        style={{ width: '100%', height: '100%', minHeight: '280px' }}
        mapStyle="mapbox://styles/mapbox/outdoors-v12"
        mapboxAccessToken={MAPBOX_TOKEN}
        attributionControl={false}
      >
        {/* Route polyline */}
        <Source id="route" type="geojson" data={routeGeoJSON}>
          <Layer {...routeLayerStyle} />
        </Source>

        {/* Start marker */}
        <Marker latitude={startPoint.lat} longitude={startPoint.lng} anchor="center">
          <div
            style={{
              width: '24px',
              height: '24px',
              background: '#00ff88',
              border: '3px solid white',
              borderRadius: '50%',
              boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '10px',
              fontWeight: 'bold',
              color: 'white',
            }}
          >
            S
          </div>
        </Marker>

        {/* End marker */}
        <Marker latitude={endPoint.lat} longitude={endPoint.lng} anchor="center">
          <div
            style={{
              width: '24px',
              height: '24px',
              background: '#ff4757',
              border: '3px solid white',
              borderRadius: '50%',
              boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '10px',
              fontWeight: 'bold',
              color: 'white',
            }}
          >
            E
          </div>
        </Marker>
      </Map>
    </div>
  );
}
