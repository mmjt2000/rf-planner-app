# Copyright (c) 2026 Jean Thomas Montezuma Montreuil
# All Rights Reserved.

"""
Grille hexagonale pour placement de sites RF
Modele 3-secteurs avec calcul de couverture reelle
"""
import math


# ============================================================
# CONSTANTES GEOGRAPHIQUES
# ============================================================
EARTH_RADIUS_KM = 6371.0
KM_PER_DEG_LAT = 111.32  # km par degre de latitude


def km_to_deg_lat(km):
    """Convertit km en degres de latitude"""
    return km / KM_PER_DEG_LAT


def km_to_deg_lon(km, latitude_deg):
    """Convertit km en degres de longitude (depend de la latitude)"""
    cos_lat = math.cos(math.radians(latitude_deg))
    if cos_lat < 0.01:
        cos_lat = 0.01
    return km / (KM_PER_DEG_LAT * cos_lat)


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance entre 2 points GPS en km"""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ============================================================
# HEXAGONE - COORDONNEES
# ============================================================
def hexagon_vertices(center_lat, center_lon, radius_km):
    """
    Retourne les 6 sommets d'un hexagone 'flat-top' oriente verticalement.
    Chaque sommet est a distance 'radius_km' du centre.
    """
    vertices = []
    for i in range(6):
        angle_deg = 60 * i - 30  # -30 pour flat-top
        angle_rad = math.radians(angle_deg)
        dlat = km_to_deg_lat(radius_km * math.cos(angle_rad))
        dlon = km_to_deg_lon(radius_km * math.sin(angle_rad), center_lat)
        vertices.append([center_lon + dlon, center_lat + dlat])  # [lon, lat] pour GeoJSON
    vertices.append(vertices[0])  # Fermer le polygone
    return vertices


# ============================================================
# GRILLE HEXAGONALE
# ============================================================
def generate_hex_grid(center_lat, center_lon, radius_km, target_area_km2):
    """
    Genere une grille hexagonale couvrant target_area_km2.
    
    Args:
        center_lat, center_lon : centre de la zone
        radius_km              : rayon d'une cellule
        target_area_km2        : surface a couvrir
    
    Returns:
        {
            "cells": [{"lat": ..., "lon": ..., "hex_geojson": {...}}, ...],
            "count": N,
            "total_area_km2": A,
            "efficiency_pct": X
        }
    """
    # Aire d'un hexagone
    hex_area = (3 * math.sqrt(3) / 2) * (radius_km ** 2)
    
    # Nombre de cellules necessaires (avec overlap factor)
    overlap_factor = 0.65
    n_cells = max(1, math.ceil(target_area_km2 / (hex_area * overlap_factor)))
    
    # Distance entre centres de cellules adjacentes (flat-top)
    # d = sqrt(3) * R
    d_km = math.sqrt(3) * radius_km
    
    # Convertir en degres
    dlat = km_to_deg_lat(d_km)
    dlon = km_to_deg_lon(d_km, center_lat)
    
    cells = []
    
    # Generer les centres en spirale autour du centre
    # Methode : boucle sur une grille puis tri par distance
    grid_radius = math.ceil(math.sqrt(n_cells)) + 1
    
    candidates = []
    for i in range(-grid_radius, grid_radius + 1):
        for j in range(-grid_radius, grid_radius + 1):
            # Coordonnees axiales -> cartesiennes (flat-top)
            lat = center_lat + i * dlat
            lon = center_lon + j * dlon * 1.5  # 1.5 car axial coords
            dist = haversine_km(center_lat, center_lon, lat, lon)
            candidates.append((dist, lat, lon))
    
    # Trier par distance au centre
    candidates.sort(key=lambda x: x[0])
    
    # Prendre les N premiers
    for idx, (dist, lat, lon) in enumerate(candidates[:n_cells]):
        cells.append({
            "site_id": f"SITE_{idx+1:03d}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "distance_from_center_km": round(dist, 3),
            "hex_geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [hexagon_vertices(lat, lon, radius_km)]
                },
                "properties": {
                    "site_id": f"SITE_{idx+1:03d}",
                    "index": idx
                }
            }
        })
    
    total_area = n_cells * hex_area
    efficiency = (target_area_km2 / total_area) * 100 if total_area > 0 else 0
    
    return {
        "cells": cells,
        "count": n_cells,
        "total_area_km2": round(total_area, 2),
        "target_area_km2": target_area_km2,
        "hex_area_km2": round(hex_area, 4),
        "efficiency_pct": round(efficiency, 1),
        "overlap_factor": overlap_factor,
    }


# ============================================================
# DETECTION OVERLAP
# ============================================================
def detect_overlaps(cells, radius_km):
    """
    Detecte les paires de cellules qui se chevauchent trop.
    (distance entre centres < 2*R)
    """
    overlaps = []
    threshold_km = 1.7 * radius_km  # Seuil (1.7 = overlap modere)
    
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            d = haversine_km(
                cells[i]["lat"], cells[i]["lon"],
                cells[j]["lat"], cells[j]["lon"]
            )
            if d < threshold_km:
                overlaps.append({
                    "cell_a": cells[i]["site_id"],
                    "cell_b": cells[j]["site_id"],
                    "distance_km": round(d, 3),
                    "severity": "high" if d < radius_km else "moderate"
                })
    
    return overlaps


# ============================================================
# DETECTION TROUS DE COUVERTURE
# ============================================================
def detect_coverage_holes(cells, center_lat, center_lon, target_area_km2, radius_km):
    """
    Estime les zones non couvertes par les cellules.
    Methode simple : verifier si la zone cible est couverte.
    """
    # Aire effective couverte par les cellules
    hex_area = (3 * math.sqrt(3) / 2) * (radius_km ** 2)
    covered_area = len(cells) * hex_area
    
    # Tolerance (overlap)
    effective_covered = covered_area * 0.85
    
    coverage_pct = min(100, (effective_covered / target_area_km2) * 100)
    holes_pct = 100 - coverage_pct
    
    return {
        "coverage_pct": round(coverage_pct, 1),
        "holes_pct": round(holes_pct, 1),
        "covered_km2": round(effective_covered, 2),
        "uncovered_km2": round(max(0, target_area_km2 - effective_covered), 2),
    }


# ============================================================
# FONCTION PRINCIPALE
# ============================================================
def plan_sites(center_lat, center_lon, radius_km, target_area_km2):
    """
    Planifie les sites et retourne le resultat complet.
    """
    grid = generate_hex_grid(center_lat, center_lon, radius_km, target_area_km2)
    overlaps = detect_overlaps(grid["cells"], radius_km)
    coverage = detect_coverage_holes(grid["cells"], center_lat, center_lon, target_area_km2, radius_km)
    
    # GeoJSON FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "features": [cell["hex_geojson"] for cell in grid["cells"]]
    }
    
    return {
        "center": {"lat": center_lat, "lon": center_lon},
        "radius_km": radius_km,
        "n_sites": grid["count"],
        "hex_area_km2": grid["hex_area_km2"],
        "total_area_km2": grid["total_area_km2"],
        "efficiency_pct": grid["efficiency_pct"],
        "coverage": coverage,
        "overlaps_count": len(overlaps),
        "overlaps": overlaps[:10],  # Top 10 pour ne pas surcharger
        "sites": [
            {
                "site_id": c["site_id"],
                "lat": c["lat"],
                "lon": c["lon"],
                "distance_from_center_km": c["distance_from_center_km"],
            }
            for c in grid["cells"]
        ],
        "geojson": geojson,
    }
