import { useMemo, useRef, useCallback } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import type { LayerProps, MapRef } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import type { ActivitySample } from '../../types/api';

const MAPBOX_TOKEN = 'pk.eyJ1Ijoia25lY2h0MDEwMiIsImEiOiJjbWpyZXlubGI0ZnZwM2NxM3pkaWFya3QzIn0.mLS4t_0PeqoqN4rI9pOnqA';

interface ActivityMapProps {
  samples: ActivitySample[];
  className?: string;
}

// Route line style - 주황색으로 강변/물가에서도 잘 보이도록
const routeLayerStyle: LayerProps = {
  id: 'route',
  type: 'line',
  paint: {
    'line-color': '#ff6b35',
    'line-width': 4,
    'line-opacity': 0.95,
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

  // Calculate bounds for fitting the entire route
  const bounds = useMemo(() => {
    if (gpsPoints.length < 2) {
      return null;
    }

    const lats = gpsPoints.map((p) => p.lat);
    const lngs = gpsPoints.map((p) => p.lng);

    return {
      minLng: Math.min(...lngs),
      maxLng: Math.max(...lngs),
      minLat: Math.min(...lats),
      maxLat: Math.max(...lats),
    };
  }, [gpsPoints]);

  // Calculate center (fallback)
  const center = useMemo(() => {
    if (!bounds) {
      return { lat: 37.5665, lng: 126.978 }; // Seoul default
    }
    return {
      lat: (bounds.minLat + bounds.maxLat) / 2,
      lng: (bounds.minLng + bounds.maxLng) / 2,
    };
  }, [bounds]);

  // Map reference for fitBounds
  const mapRef = useRef<MapRef>(null);

  // Fit map to route bounds when map loads
  const onMapLoad = useCallback(() => {
    if (mapRef.current && bounds) {
      mapRef.current.fitBounds(
        [
          [bounds.minLng, bounds.minLat],
          [bounds.maxLng, bounds.maxLat],
        ],
        {
          padding: { top: 50, bottom: 50, left: 50, right: 50 },
          duration: 0,
        }
      );
    }
  }, [bounds]);

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

  // GPS 데이터가 없으면 아무것도 렌더링하지 않음
  if (gpsPoints.length < 2) {
    return null;
  }

  const startPoint = gpsPoints[0];
  const endPoint = gpsPoints[gpsPoints.length - 1];

  return (
    <div className={`card overflow-hidden p-0 ${className}`} style={{ height: '100%' }}>
      <Map
        ref={mapRef}
        initialViewState={{
          latitude: center.lat,
          longitude: center.lng,
          zoom: 14,
        }}
        onLoad={onMapLoad}
        style={{ width: '100%', height: '100%' }}
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
