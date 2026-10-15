import math
import geopandas as gpd
from shapely.geometry import Polygon
import json

def generate_hexagon_grid(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    num_rings: int = 2
) -> dict:
    """
    Génère une grille hexagonale centrée sur un point.
    Retourne un GeoJSON.
    """
    hex_radius_m = radius_km * 1000
    spacing_m = hex_radius_m * math.sqrt(3)
    
    hexagons = []
    
    for ring in range(num_rings + 1):
        if ring == 0:
            centers = [(0, 0)]
        else:
            centers = []
            for i in range(6):
                angle = math.radians(60 * i)
                x = ring * spacing_m * math.cos(angle)
                y = ring * spacing_m * math.sin(angle)
                centers.append((x, y))
                
                for j in range(1, ring):
                    next_angle = math.radians(60 * ((i + 1) % 6))
                    nx = ring * spacing_m * math.cos(next_angle)
                    ny = ring * spacing_m * math.sin(next_angle)
                    interp_x = x + (nx - x) * (j / ring)
                    interp_y = y + (ny - y) * (j / ring)
                    centers.append((interp_x, interp_y))
        
        for x, y in centers:
            points = []
            for i in range(6):
                angle = math.radians(60 * i + 30)
                px = x + hex_radius_m * math.cos(angle)
                py = y + hex_radius_m * math.sin(angle)
                lon = center_lon + (px / 111320) / math.cos(math.radians(center_lat))
                lat = center_lat + (py / 110540)
                points.append((lon, lat))
            
            polygon = Polygon(points)
            hexagons.append(polygon)
    
    gdf = gpd.GeoDataFrame(geometry=hexagons, crs="EPSG:4326")
    geojson_data = json.loads(gdf.to_json())
    
    return geojson_data