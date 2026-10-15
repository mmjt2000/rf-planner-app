# serveur_simple.py - Fichier unique, autonome, prêt pour Render
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import math
import httpx
import urllib.parse
import os

app = FastAPI(title="RF Planner - Serveur Simplifié", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir les fichiers frontend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "RF Planner API is running. Frontend not found."}

@app.get("/{page_name}")
async def serve_page(page_name: str):
    file_path = os.path.join(FRONTEND_DIR, f"{page_name}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Page not found")

# ==========================================
# MODÈLES PYDANTIC
# ==========================================
class LinkBudgetRequest(BaseModel):
    center_lat: float
    center_lon: float
    frequency_mhz: float
    antenna_height_m: float
    clutter_loss_db: float
    propagation_model: str
    target_area_km2: float

class NeighborRequest(BaseModel):
    source_site_id: str
    detection_radius_m: float = 2000.0
    vendor: str = "Huawei"

class PCIRequest(BaseModel):
    vendor: str = "Huawei"

class NominalRequest(BaseModel):
    zone_type: str = "Dense_Urban"

class ScenarioRequest(BaseModel):
    scenario_a: dict
    scenario_b: dict
    target_area_km2: float = 100.0
    population: int = 150000

class TerrainRequest(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

# ==========================================
# DONNÉES SIMULÉES
# ==========================================
MOCK_SITES = [
    {"site_id": "MTL_5G_001", "lat": 48.4284, "lon": -71.0656, "pci": 10, "cell_id": 1},
    {"site_id": "MTL_5G_002", "lat": 48.4350, "lon": -71.0550, "pci": 11, "cell_id": 2},
    {"site_id": "MTL_5G_003", "lat": 48.4200, "lon": -71.0750, "pci": 13, "cell_id": 3},
]
MOCK_NEIGHBORS = {"MTL_5G_001": ["MTL_5G_002", "MTL_5G_003"]}

# ==========================================
# ENDPOINT 1 & 2 : LINK BUDGET
# ==========================================
@app.post("/api/v1/link-budget")
async def calculate_link_budget(req: LinkBudgetRequest):
    tx_power = 43.0
    rx_sensitivity = -95.0
    antenna_gain = 18.0 if req.frequency_mhz > 2000 else 16.0
    margin = 11.0
    
    mapl = tx_power + antenna_gain - rx_sensitivity - margin - req.clutter_loss_db
    
    if req.propagation_model == "cost231":
        radius_km = max(0.2, (mapl - 120) / 40)
    else:
        radius_km = max(0.5, (mapl - 110) / 35)
        
    hex_area = (3 * math.sqrt(3) / 2) * (radius_km ** 2)
    estimated_sites = math.ceil(req.target_area_km2 / (hex_area * 0.65))
    
    lat, lon = req.center_lat, req.center_lon
    r = radius_km * 0.009
    
    hexagons = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [lon, lat + r], [lon + r*0.866, lat + r*0.5],
                    [lon + r*0.866, lat - r*0.5], [lon, lat - r],
                    [lon - r*0.866, lat - r*0.5], [lon - r*0.866, lat + r*0.5],
                    [lon, lat + r]
                ]]
            },
            "properties": {}
        }]
    }
    
    return {
        "mapl_db": round(mapl, 1),
        "radius_km": round(radius_km, 2),
        "estimated_sites": estimated_sites,
        "hexagons_geojson": hexagons
    }

# ==========================================
# ENDPOINT 3 : VOISINAGE
# ==========================================
@app.post("/api/v1/neighbors")
async def plan_neighbors(req: NeighborRequest):
    source = next((s for s in MOCK_SITES if s["site_id"] == req.source_site_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="Site non trouvé")
    
    neighbors = [{"site_id": "MTL_5G_002", "distance_m": 1200, "pci": 11, "cell_id": 2, "pci_conflict_mod3": False}]
    
    script = f"# Script {req.vendor}\nADD GNBRELATION: LocalCellId={source['cell_id']}, NrNeighborCellId=2, NrPci=11, Switch=ON;"
    return {"source_site": source, "neighbors": neighbors, "vendor_script": script}

# ==========================================
# ENDPOINT 4 : PCI PLANNING
# ==========================================
@app.post("/api/v1/pci-planning")
async def plan_pci(req: PCIRequest):
    sites_result = []
    for i, site in enumerate(MOCK_SITES):
        assigned_pci = (site["pci"] + (i * 3)) % 1008
        sites_result.append({
            **site,
            "assigned_pci": assigned_pci,
            "prach_root": (assigned_pci * 7) % 838,
            "tac": 1000 + (i // 2)
        })
    
    script = f"# Script PCI {req.vendor}\n" + "\n".join([f"MOD NRCELL: LocalCellId={s['cell_id']}, PhyCellId={s['assigned_pci']}, Tac={s['tac']};" for s in sites_result])
    
    return {
        "sites": sites_result,
        "script": script,
        "conflicts": [],
        "stats": {"total_sites": len(sites_result), "unique_pcis": len(sites_result), "tacs_used": len(set(s["tac"] for s in sites_result))}
    }

# ==========================================
# ENDPOINT 5 : NOMINAL PLANNING
# ==========================================
@app.post("/api/v1/nominal-planning")
async def generate_nominal_plan(req: NominalRequest):
    rules = {
        "Dense_Urban": {"height": 25, "mech_tilt": 6, "elec_tilt": 4, "power": 40, "azimuth_step": 120},
        "Suburban": {"height": 35, "mech_tilt": 3, "elec_tilt": 2, "power": 43, "azimuth_step": 120},
        "Rural": {"height": 45, "mech_tilt": 0, "elec_tilt": 0, "power": 46, "azimuth_step": 120}
    }
    
    rule = rules.get(req.zone_type, rules["Suburban"])
    nominal_sites = []
    
    base_azimuth = 0
    for i in range(3):
        site_id = f"MTL_5G_NOM_{i+1:03d}"
        azimuth = (base_azimuth + (i * rule["azimuth_step"])) % 360
        
        nominal_sites.append({
            "site_id": site_id,
            "lat": 48.4284 + (i * 0.005),
            "lon": -71.0656 + (i * 0.005),
            "azimuth_deg": azimuth,
            "mech_tilt_deg": rule["mech_tilt"],
            "elec_tilt_deg": rule["elec_tilt"],
            "height_m": rule["height"],
            "tx_power_dbm": rule["power"],
            "antenna_type": "Massive MIMO 64T64R" if req.zone_type == "Dense_Urban" else "Standard 4T4R"
        })
    
    csv_lines = ["Site ID,Latitude,Longitude,Azimuth (°),Méca Tilt (°),Élec Tilt (°),Hauteur (m),Puissance (dBm),Type Antenne"]
    for s in nominal_sites:
        csv_lines.append(f"{s['site_id']},{s['lat']},{s['lon']},{s['azimuth_deg']},{s['mech_tilt_deg']},{s['elec_tilt_deg']},{s['height_m']},{s['tx_power_dbm']},{s['antenna_type']}")
    
    return {
        "sites": nominal_sites,
        "csv_export": "\n".join(csv_lines),
        "zone_applied": req.zone_type
    }

# ==========================================
# ENDPOINT 6 : SIMULATEUR DE SCÉNARIOS
# ==========================================
@app.post("/api/v1/scenario-simulator")
async def simulate_scenarios(req: ScenarioRequest):
    def calc_metrics(s, area, pop):
        n = s["num_sites"]
        band = float(s["band"])
        zone = s["zone"]
        
        base_radius = {"Dense_Urban": 0.5, "Suburban": 1.2, "Rural": 3.0}
        r = base_radius.get(zone, 1.0) * (3500 / band) ** 0.5
        
        hex_area = (3 * math.sqrt(3) / 2) * (r ** 2)
        coverage_pct = min(98.0, (n * hex_area * 0.65 / area) * 100)
        
        capacity_per_site = {"Dense_Urban": 1.0, "Suburban": 0.7, "Rural": 0.4}
        total_capacity_gbps = n * capacity_per_site.get(zone, 0.7)
        capacity_per_user_mbps = (total_capacity_gbps * 1000) / pop if pop > 0 else 0
        
        cost_per_site = {"Dense_Urban": 180000, "Suburban": 120000, "Rural": 90000}
        capex_usd = n * cost_per_site.get(zone, 120000)
        opex_annual_usd = capex_usd * 0.12
        
        sinr_db = 25 - (n / area) * 2
        
        arpu_monthly = 15
        revenue_annual = pop * 0.30 * arpu_monthly * 12
        payback_years = capex_usd / revenue_annual if revenue_annual > 0 else 99
        
        return {
            "name": s["name"],
            "num_sites": n,
            "radius_km": round(r, 2),
            "coverage_pct": round(coverage_pct, 1),
            "total_capacity_gbps": round(total_capacity_gbps, 1),
            "capacity_per_user_mbps": round(capacity_per_user_mbps, 2),
            "capex_usd": int(capex_usd),
            "opex_annual_usd": int(opex_annual_usd),
            "avg_sinr_db": round(sinr_db, 1),
            "payback_years": round(payback_years, 1),
            "cost_per_covered_user_usd": round(capex_usd / (pop * coverage_pct / 100), 2) if coverage_pct > 0 else 0
        }
    
    metrics_a = calc_metrics(req.scenario_a, req.target_area_km2, req.population)
    metrics_b = calc_metrics(req.scenario_b, req.target_area_km2, req.population)
    
    winner = metrics_a if metrics_a["coverage_pct"] > metrics_b["coverage_pct"] else metrics_b
    recommendation = f"Le scénario '{winner['name']}' offre la meilleure couverture ({winner['coverage_pct']}%) avec un payback de {winner['payback_years']} ans."
    
    return {
        "scenario_a": metrics_a,
        "scenario_b": metrics_b,
        "recommendation": recommendation,
        "target_area_km2": req.target_area_km2,
        "population": req.population
    }

# ==========================================
# ENDPOINT 7 : IMPORT TERRAIN RÉEL (Mode démo)
# ==========================================
@app.post("/api/v1/terrain-import")
async def import_real_terrain(req: TerrainRequest):
    import random
    random.seed(42)
    
    features = []
    
    def is_in_river(lat, lon):
        river_lat_min = 48.418
        river_lat_max = 48.435
        river_lon_min = -71.080
        river_lon_max = -71.050
        return (river_lat_min <= lat <= river_lat_max and 
                river_lon_min <= lon <= river_lon_max)
    
    num_buildings = 150
    attempts = 0
    while len(features) < num_buildings and attempts < 500:
        attempts += 1
        lat = random.uniform(req.min_lat, req.max_lat)
        lon = random.uniform(req.min_lon, req.max_lon)
        
        if is_in_river(lat, lon):
            continue
        
        size = random.uniform(0.0001, 0.0003)
        
        coords = [
            [lon, lat],
            [lon + size, lat],
            [lon + size, lat + size],
            [lon, lat + size],
            [lon, lat]
        ]
        
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "type": "building",
                "loss_db": 15.0,
                "color": "#94a3b8"
            }
        })
    
    num_forests = 8
    attempts = 0
    while len([f for f in features if f['properties']['type'] == 'forest']) < num_forests and attempts < 100:
        attempts += 1
        lat = random.uniform(req.min_lat, req.max_lat)
        lon = random.uniform(req.min_lon, req.max_lon)
        
        if is_in_river(lat, lon):
            continue
            
        size = random.uniform(0.001, 0.003)
        
        coords = [
            [lon, lat],
            [lon + size, lat],
            [lon + size, lat + size],
            [lon, lat + size],
            [lon, lat]
        ]
        
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "type": "forest",
                "loss_db": 10.0,
                "color": "#166534"
            }
        })
    
    print(f"✅ Mode démo: {len(features)} obstacles générés")
    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "message": f"Mode démonstration : {len(features)} obstacles simulés."
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "RF Planner API is running"}