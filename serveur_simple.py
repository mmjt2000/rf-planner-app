# serveur_simple.py - Fichier unique, autonome, prêt pour Render
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import math
import httpx
import propagation
import hexagonal
import urllib.parse
import os
import asyncio

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
    if page_name.endswith('.html'):
        page_name = page_name[:-5]
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
    target_area_km2: float
    frequency_mhz: float = 3500.0
    bandwidth_mhz: float = 100.0
    antenna_height_m: float = 30.0
    mobile_height_m: float = 1.5
    tx_power_dbm: float = 43.0
    tx_antenna_gain_dbi: float = 18.0
    tx_cable_loss_db: float = 2.0
    rx_sensitivity_dbm: float = -95.0
    rx_antenna_gain_dbi: float = 0.0
    rx_cable_loss_db: float = 0.0
    interference_margin_db: float = 3.0
    shadowing_margin_db: float = 8.0
    body_loss_db: float = 0.0
    environment: str = "suburban"
    propagation_model: str = "auto"
    clutter_loss_db: float = 0.0
    overlap_factor: float = 0.65

class PlanSitesRequest(BaseModel):
    center_lat: float
    center_lon: float
    radius_km: float
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
# 🧠 MÉMOIRE PARTAGÉE (entre modules)
# ==========================================
# Stocke les sites générés par /api/v1/plan-sites
# Utilisé par /api/v1/pci-planning et /api/v1/neighbors
_LAST_PLANNED_SITES = []

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
    if req.propagation_model == "auto":
        model = propagation.select_best_model(req.frequency_mhz, req.environment)
    else:
        model = req.propagation_model
    
    mapl_result = propagation.calculate_mapl(
        tx_power_dbm=req.tx_power_dbm,
        tx_antenna_gain_dbi=req.tx_antenna_gain_dbi,
        tx_cable_loss_db=req.tx_cable_loss_db,
        rx_antenna_gain_dbi=req.rx_antenna_gain_dbi,
        rx_cable_loss_db=req.rx_cable_loss_db,
        rx_sensitivity_dbm=req.rx_sensitivity_dbm,
        interference_margin_db=req.interference_margin_db,
        shadowing_margin_db=req.shadowing_margin_db,
        body_loss_db=req.body_loss_db
    )
    
    mapl_db = mapl_result["mapl_db"] - req.clutter_loss_db
    
    radius_km = propagation.calculate_radius_km(
        mapl_db=mapl_db,
        freq_mhz=req.frequency_mhz,
        hb_m=req.antenna_height_m,
        hm_m=req.mobile_height_m,
        model=model,
        environment=req.environment
    )
    
    sites_result = propagation.estimate_sites_hexagonal(
        target_area_km2=req.target_area_km2,
        radius_km=radius_km,
        overlap_factor=req.overlap_factor
    )
    
    lat, lon = req.center_lat, req.center_lon
    r = radius_km * 0.009
    
    def make_hex(center_lat, center_lon, radius):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [center_lon, center_lat + radius],
                    [center_lon + radius * 0.866, center_lat + radius * 0.5],
                    [center_lon + radius * 0.866, center_lat - radius * 0.5],
                    [center_lon, center_lat - radius],
                    [center_lon - radius * 0.866, center_lat - radius * 0.5],
                    [center_lon - radius * 0.866, center_lat + radius * 0.5],
                    [center_lon, center_lat + radius]
                ]]
            },
            "properties": {}
        }
    
    hexagons = {
        "type": "FeatureCollection",
        "features": [make_hex(lat, lon, r)]
    }
    
    return {
        "model": model,
        "frequency_mhz": req.frequency_mhz,
        "environment": req.environment,
        "mapl_db": round(mapl_db, 1),
        "eirp_dbm": mapl_result["eirp_dbm"],
        "radius_km": radius_km,
        "estimated_sites": sites_result["sites"],
        "hex_area_km2": sites_result["hex_area_km2"],
        "breakdown": {
            "tx_power_dbm": req.tx_power_dbm,
            "tx_antenna_gain_dbi": req.tx_antenna_gain_dbi,
            "tx_cable_loss_db": req.tx_cable_loss_db,
            "rx_sensitivity_dbm": req.rx_sensitivity_dbm,
            "margins_db": mapl_result["margins_db"],
            "clutter_loss_db": req.clutter_loss_db,
        },
        "hexagons_geojson": hexagons
    }

# ==========================================
# ENDPOINT PLAN-SITES : Placement hexagonal
# ==========================================
@app.post("/api/v1/plan-sites")
async def plan_sites_endpoint(req: PlanSitesRequest):
    """
    Genere une grille hexagonale de sites pour couvrir une zone.
    Sauvegarde en mémoire pour PCI/Neighbor.
    """
    global _LAST_PLANNED_SITES
    result = hexagonal.plan_sites(
        center_lat=req.center_lat,
        center_lon=req.center_lon,
        radius_km=req.radius_km,
        target_area_km2=req.target_area_km2
    )
    # 🧠 Sauvegarde en mémoire pour les modules PCI/Voisinage
    if result.get("sites"):
        _LAST_PLANNED_SITES = result["sites"]
        print(f"🧠 {len(_LAST_PLANNED_SITES)} sites sauvegardés pour PCI/Voisinage")
    return result

# ==========================================
# ENDPOINT 3 : VOISINAGE (avec vrais 98 sites)
# ==========================================
@app.post("/api/v1/neighbors")
async def plan_neighbors(req: NeighborRequest):
    """
    Détection de voisinage avec détection de conflits PCI.
    NE SUPPRIME PAS les voisins en conflit : les SIGNALE (bonne pratique RF).
    """
    global _LAST_PLANNED_SITES
    sites = _LAST_PLANNED_SITES if _LAST_PLANNED_SITES else MOCK_SITES
    
    source = next((s for s in sites if s.get("site_id") == req.source_site_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="Site non trouvé")
    
    def get_pci(site):
        pci = site.get("assigned_pci")
        if pci is None:
            pci = site.get("pci", 0)
        return pci
    
    src_pci = get_pci(source)
    src_cell_id = source.get("cell_id", 1)
    
    # Détection de TOUS les voisins dans le rayon
    neighbors = []
    for i, s in enumerate(sites):
        if s.get("site_id") == req.source_site_id:
            continue
        
        dist_m = haversine_m(source["lat"], source["lon"], s["lat"], s["lon"])
        
        if dist_m <= req.detection_radius_m:
            s_pci = get_pci(s)
            s_cell_id = s.get("cell_id", i + 1)
            
            # Détection des conflits (à titre informatif)
            conflict_pci = (src_pci == s_pci)
            conflict_mod3 = ((src_pci % 3) == (s_pci % 3))
            conflict_mod30 = ((src_pci % 30) == (s_pci % 30))
            
            if conflict_pci:
                conflict_level = "CRITICAL"
                conflict_msg = "PCI identique"
            elif conflict_mod3:
                conflict_level = "HIGH"
                conflict_msg = "Conflit Mod-3 (PSS)"
            elif conflict_mod30:
                conflict_level = "MEDIUM"
                conflict_msg = "Conflit Mod-30 (DMRS)"
            else:
                conflict_level = "OK"
                conflict_msg = None
            
            neighbors.append({
                "site_id": s["site_id"],
                "distance_m": round(dist_m, 0),
                "pci": s_pci,
                "cell_id": s_cell_id,
                "tac": s.get("tac", 0),
                "conflict": conflict_level,
                "conflict_msg": conflict_msg,
            })
    
    neighbors.sort(key=lambda x: x["distance_m"])
    
    # Classification
    ok_neighbors = [n for n in neighbors if n["conflict"] == "OK"]
    conflict_neighbors = [n for n in neighbors if n["conflict"] != "OK"]
    
    # Génération du script vendor
    vendor = req.vendor
    lines = []
    lines.append("# " + "=" * 60)
    lines.append(f"# Script Voisinage {vendor} - Source: {req.source_site_id}")
    lines.append(f"# PCI source: {src_pci} | CellId: {src_cell_id}")
    lines.append(f"# Rayon de détection: {req.detection_radius_m} m")
    lines.append(f"# Voisins détectés: {len(neighbors)}")
    lines.append(f"#   ✅ Sans conflit: {len(ok_neighbors)}")
    lines.append(f"#   ⚠️  Avec conflit: {len(conflict_neighbors)}")
    lines.append("# " + "=" * 60)
    lines.append("")
    
    # --- AVERTISSEMENTS ---
    if conflict_neighbors:
        lines.append("# " + "!" * 60)
        lines.append("# ⚠️  AVERTISSEMENTS — Conflits PCI détectés")
        lines.append("# " + "!" * 60)
        lines.append("# Ces relations NE SONT PAS ajoutées automatiquement.")
        lines.append("# Il faut d'abord optimiser les PCI (module PCI / PRACH) :")
        lines.append("#")
        for n in conflict_neighbors:
            lines.append(f"#   ❌ {n['site_id']} (PCI {n['pci']}, dist {n['distance_m']} m) → {n['conflict_msg']}")
        lines.append("#")
        lines.append("# " + "!" * 60)
        lines.append("")
    
    # --- RELATIONS OK ---
    lines.append(f"# ✅ {len(ok_neighbors)} relations à ajouter :")
    lines.append("")
    
    for n in ok_neighbors:
        if vendor == "Huawei":
            lines.append(f"ADD GNBRELATION: LocalCellId={src_cell_id}, NrNeighborCellId={n['cell_id']}, NrPci={n['pci']}, Switch=ON;")
        elif vendor == "Ericsson":
            lines.append(f"set GNBRelation={src_cell_id} neighborCellId {n['cell_id']} neighborPci {n['pci']} isHoAllowed true")
        elif vendor == "Nokia":
            lines.append(f"configure nr relation {src_cell_id} {n['cell_id']} pci {n['pci']} enable")
        elif vendor == "Samsung":
            lines.append(f"ADD NRNEIGHBOR: SrcCell={src_cell_id}, NbrCell={n['cell_id']}, NbrPci={n['pci']}")
        else:
            lines.append(f"NEIGHBOR {src_cell_id} -> {n['cell_id']} (PCI {n['pci']})")
    
    script = "\n".join(lines)
    
    return {
        "source_site": source,
        "neighbors": neighbors,
        "ok_neighbors": ok_neighbors,
        "conflict_neighbors": conflict_neighbors,
        "vendor_script": script,
        "summary": {
            "total": len(neighbors),
            "ok": len(ok_neighbors),
            "conflicts": len(conflict_neighbors),
        }
    }
# ==========================================
# ENDPOINT 4 : PCI PLANNING (algorithme de coloration)
# ==========================================
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def build_neighbor_graph(sites, threshold_km):
    """Construit le graphe de voisinage : {site_id: [voisins]}"""
    graph = {s["site_id"]: [] for s in sites}
    n = len(sites)
    for i in range(n):
        for j in range(i+1, n):
            d_km = haversine_m(sites[i]["lat"], sites[i]["lon"],
                               sites[j]["lat"], sites[j]["lon"]) / 1000.0
            if d_km <= threshold_km:
                graph[sites[i]["site_id"]].append(sites[j]["site_id"])
                graph[sites[j]["site_id"]].append(sites[i]["site_id"])
    return graph

def assign_pci_coloring(sites, graph):
    """
    Algorithme de coloration de graphe :
    - PCI entre 0 et 503
    - Pas de conflit Mod-3 (PSS) entre voisins
    - Pas de conflit Mod-30 (DMRS) entre voisins
    - Pas de PCI identique entre voisins
    """
    pci_map = {}
    
    for site in sites:
        sid = site["site_id"]
        used_pcis = set()
        used_mod3 = set()
        used_mod30 = set()
        
        for neighbor_id in graph.get(sid, []):
            if neighbor_id in pci_map:
                n_pci = pci_map[neighbor_id]
                used_pcis.add(n_pci)
                used_mod3.add(n_pci % 3)
                used_mod30.add(n_pci % 30)
        
        # Chercher le premier PCI disponible
        for pci in range(504):
            if pci in used_pcis:
                continue
            if (pci % 3) in used_mod3:
                continue
            if (pci % 30) in used_mod30:
                continue
            pci_map[sid] = pci
            break
        else:
            # Fallback : prendre un PCI non utilisé
            for pci in range(504):
                if pci not in used_pcis:
                    pci_map[sid] = pci
                    break
            else:
                pci_map[sid] = 0
    
    return pci_map

def assign_prach_roots(sites, graph):
    """
    Attribution PRACH root sequence (0-837).
    Évite les collisions entre voisins.
    """
    prach_map = {}
    
    for site in sites:
        sid = site["site_id"]
        used_roots = set()
        
        for neighbor_id in graph.get(sid, []):
            if neighbor_id in prach_map:
                used_roots.add(prach_map[neighbor_id])
        
        for root in range(838):
            if root not in used_roots:
                prach_map[sid] = root
                break
        else:
            prach_map[sid] = 0
    
    return prach_map

def assign_tacs(sites, grid_size_km=8.0):
    """
    Regroupement TAC par grille géographique.
    grid_size_km : taille d'une cellule TAC (défaut 8 km).
    Tous les sites dans la même cellule → même TAC.
    """
    tac_map = {}
    tac_counter = 1000
    grid_assignments = {}
    
    for site in sites:
        # Grille en degrés (~111 km par degré lat)
        # On utilise une grille décalée pour éviter les bords
        deg_size = grid_size_km / 111.0
        
        grid_x = int(math.floor(site["lon"] / deg_size))
        grid_y = int(math.floor(site["lat"] / deg_size))
        grid_key = (grid_x, grid_y)
        
        if grid_key not in grid_assignments:
            grid_assignments[grid_key] = tac_counter
            tac_counter += 1
        
        tac_map[site["site_id"]] = grid_assignments[grid_key]
    
    return tac_map

def generate_vendor_script(sites_result, vendor):
    """Genere le script de configuration par vendor."""
    lines = [f"# ============================================",
             f"# Script PCI - {vendor}",
             f"# Total sites : {len(sites_result)}",
             f"# Genere automatiquement par RF Planner",
             f"# ============================================",
             ""]
    
    if vendor == "Huawei":
        for s in sites_result:
            lines.append(f"MOD NRCELL: LocalCellId={s['cell_id']}, PhyCellId={s['assigned_pci']}, Tac={s['tac']}, RootSequenceId={s['prach_root']};")
    elif vendor == "Ericsson":
        for s in sites_result:
            lines.append(f"set NRCell={s['cell_id']} physicalCellId {s['assigned_pci']} trackingAreaCode {s['tac']} prachRootSequence {s['prach_root']}")
    elif vendor == "Nokia":
        for s in sites_result:
            lines.append(f"configure nr cell {s['cell_id']} pci {s['assigned_pci']} tac {s['tac']} prach-root {s['prach_root']}")
    else:
        for s in sites_result:
            lines.append(f"CELL {s['cell_id']} PCI={s['assigned_pci']} TAC={s['tac']} PRACH={s['prach_root']}")
    
    return "\n".join(lines)

@app.post("/api/v1/pci-planning")
async def plan_pci(req: PCIRequest):
    global _LAST_PLANNED_SITES
    
    if _LAST_PLANNED_SITES:
        sites_input = _LAST_PLANNED_SITES
        print(f"🧠 PCI Planning sur {len(sites_input)} sites réels")
    else:
        sites_input = MOCK_SITES
        print(f"⚠️ PCI Planning sur {len(sites_input)} sites MOCK")
    
    # Graphe de voisinage
    if len(sites_input) > 1:
        dists = []
        for i in range(min(len(sites_input), 100)):
            for j in range(i+1, min(len(sites_input), 100)):
                dists.append(haversine_m(sites_input[i]["lat"], sites_input[i]["lon"],
                                        sites_input[j]["lat"], sites_input[j]["lon"]) / 1000.0)
        avg_dist_km = sum(dists) / len(dists) if dists else 1.5
        threshold_km = max(avg_dist_km * 1.5, 1.5)
    else:
        threshold_km = 2.0
    
    graph = build_neighbor_graph(sites_input, threshold_km)
    pci_map = assign_pci_coloring(sites_input, graph)
    prach_map = assign_prach_roots(sites_input, graph)
    tac_map = assign_tacs(sites_input, grid_size_km=8.0)
    
    sites_result = []
    conflicts = []
    
    for i, site in enumerate(sites_input):
        sid = site["site_id"]
        assigned_pci = pci_map[sid]
        site_out = {
            **site,
            "cell_id": i + 1,
            "assigned_pci": assigned_pci,
            "prach_root": prach_map[sid],
            "tac": tac_map[sid],
        }
        sites_result.append(site_out)
    
    for site in sites_result:
        sid = site["site_id"]
        for neighbor_id in graph.get(sid, []):
            neighbor = next((s for s in sites_result if s["site_id"] == neighbor_id), None)
            if not neighbor:
                continue
            if site["assigned_pci"] == neighbor["assigned_pci"]:
                conflicts.append({"type": "PCI_IDENTIQUE", "sites": [sid, neighbor_id]})
            elif (site["assigned_pci"] % 3) == (neighbor["assigned_pci"] % 3):
                conflicts.append({"type": "CONFLIT_MOD3", "sites": [sid, neighbor_id]})
            elif (site["assigned_pci"] % 30) == (neighbor["assigned_pci"] % 30):
                conflicts.append({"type": "CONFLIT_MOD30", "sites": [sid, neighbor_id]})
    
    seen = set()
    unique_conflicts = []
    for c in conflicts:
        key = tuple(sorted(c["sites"]))
        if key not in seen:
            seen.add(key)
            unique_conflicts.append(c)
    
    script = generate_vendor_script(sites_result, req.vendor)
    
    # 🧠 SAUVEGARDER les sites AVEC PCI pour Voisinage
    _LAST_PLANNED_SITES = sites_result
    print(f"🧠 {len(sites_result)} sites avec PCI sauvegardés pour Voisinage")
    
    return {
        "sites": sites_result,
        "script": script,
        "conflicts": unique_conflicts,
        "stats": {
            "total_sites": len(sites_result),
            "unique_pcis": len(set(s["assigned_pci"] for s in sites_result)),
            "tacs_used": len(set(s["tac"] for s in sites_result)),
            "conflicts_count": len(unique_conflicts),
            "neighbor_threshold_km": round(threshold_km, 2),
        }
    }

# ==========================================
# ENDPOINT 5 : NOMINAL PLANNING
# ==========================================
@app.post("/api/v1/nominal-planning")
async def generate_nominal_plan(req: NominalRequest):
    """
    Génère un plan nominal avec 3 ou 4 secteurs par site.
    - Dense_Urban : 4 secteurs (0/90/180/270)
    - Suburban / Rural : 3 secteurs (0/120/240)
    """
    global _LAST_PLANNED_SITES
    
    # Config par type de zone
    rules = {
        "Dense_Urban": {
            "height": 25, "mech_tilt": 6, "elec_tilt": 4, "power": 40,
            "sectors": 4, "azimuths": [0, 90, 180, 270],
            "antenna": "Massive MIMO 64T64R"
        },
        "Suburban": {
            "height": 35, "mech_tilt": 3, "elec_tilt": 2, "power": 43,
            "sectors": 3, "azimuths": [0, 120, 240],
            "antenna": "Standard 4T4R"
        },
        "Rural": {
            "height": 45, "mech_tilt": 0, "elec_tilt": 0, "power": 46,
            "sectors": 3, "azimuths": [0, 120, 240],
            "antenna": "Standard 4T4R"
        }
    }
    
    rule = rules.get(req.zone_type, rules["Suburban"])
    
    # Utiliser les 98 sites si dispo, sinon mock
    sites_input = _LAST_PLANNED_SITES if _LAST_PLANNED_SITES else [
        {"site_id": f"SITE_{i+1:03d}", "lat": 48.4284 + (i * 0.01), "lon": -71.0656}
        for i in range(5)
    ]
    
    nominal_sites = []
    for i, site in enumerate(sites_input):
        for sec_idx, azimuth in enumerate(rule["azimuths"]):
            sector_name = f"S{sec_idx + 1}"
            nominal_sites.append({
                "site_id": site["site_id"],
                "sector": sector_name,
                "cell_id": (i * rule["sectors"]) + sec_idx + 1,
                "lat": site["lat"],
                "lon": site["lon"],
                "azimuth_deg": azimuth,
                "mech_tilt_deg": rule["mech_tilt"],
                "elec_tilt_deg": rule["elec_tilt"],
                "total_tilt_deg": rule["mech_tilt"] + rule["elec_tilt"],
                "height_m": rule["height"],
                "tx_power_dbm": rule["power"],
                "antenna_type": rule["antenna"],
                "pci": site.get("assigned_pci", site.get("pci", 0)),
                "tac": site.get("tac", 1000),
            })
    
    # CSV
    csv_lines = ["site_id,sector,cell_id,lat,lon,azimuth_deg,mech_tilt_deg,elec_tilt_deg,total_tilt_deg,height_m,tx_power_dbm,antenna_type"]
    for s in nominal_sites:
        csv_lines.append(f"{s['site_id']},{s['sector']},{s['cell_id']},{s['lat']},{s['lon']},{s['azimuth_deg']},{s['mech_tilt_deg']},{s['elec_tilt_deg']},{s['total_tilt_deg']},{s['height_m']},{s['tx_power_dbm']},{s['antenna_type']}")
    
    # Stats
    unique_sites = len(set(s["site_id"] for s in nominal_sites))
    
    return {
        "sites": nominal_sites,
        "csv_export": "\n".join(csv_lines),
        "zone_applied": req.zone_type,
        "stats": {
            "total_sites": unique_sites,
            "total_sectors": len(nominal_sites),
            "sectors_per_site": rule["sectors"],
        }
    }

# ==========================================
# ENDPOINT 6 : SIMULATEUR DE SCÉNARIOS
# ==========================================
@app.post("/api/v1/scenario-simulator")
async def simulate_scenarios(req: ScenarioRequest):
    """
    Simulateur de scaling : baseline 98 sites → +X sites additionnels.
    Calcule le delta de couverture, capacité, CAPEX et ROI.
    """
    global _LAST_PLANNED_SITES
    
    # Baseline = 98 sites en mémoire (ou défaut)
    baseline_sites = len(_LAST_PLANNED_SITES) if _LAST_PLANNED_SITES else 98
    
    # Paramètres
    area_km2 = req.target_area_km2 or 100.0
    population = req.population or 150000
    
    def parse_int(v, default=10):
        try:
            return int(v) if v is not None else default
        except:
            return default
    
    def parse_float(v, default=3500.0):
        try:
            return float(v) if v is not None else default
        except:
            return default
    
    def parse_zone(v):
        return v if v in ("Dense_Urban", "Suburban", "Rural") else "Suburban"
    
    # Scénario A et B : extraire +X sites additionnels
    a = req.scenario_a or {}
    b = req.scenario_b or {}
    
    a_extra = parse_int(a.get("num_sites"), 10)
    b_extra = parse_int(b.get("num_sites"), 20)
    band = parse_float(a.get("band"), 3500.0)
    zone = parse_zone(a.get("zone", "Suburban"))
    cost_per_site = parse_float(a.get("cost_per_site"), 120000.0)
    
    def calc_metrics(n_sites, area, pop, band, zone, cost_per_site):
        base_radius = {"Dense_Urban": 0.5, "Suburban": 1.2, "Rural": 3.0}
        r = base_radius.get(zone, 1.0) * (3500 / band) ** 0.5
        
        hex_area = (3 * math.sqrt(3) / 2) * (r ** 2)
        coverage_pct = min(100.0, (n_sites * hex_area * 0.65 / area) * 100)
        
        capacity_per_site = {"Dense_Urban": 1.0, "Suburban": 0.7, "Rural": 0.4}
        total_capacity_gbps = n_sites * capacity_per_site.get(zone, 0.7)
        capacity_per_user_mbps = (total_capacity_gbps * 1000) / pop if pop > 0 else 0
        
        capex_usd = n_sites * cost_per_site
        opex_annual_usd = capex_usd * 0.12
        
        sinr_db = 25 - (n_sites / area) * 2
        
        arpu_monthly = 15
        revenue_annual = pop * 0.30 * arpu_monthly * 12
        payback_years = capex_usd / revenue_annual if revenue_annual > 0 else 99
        
        return {
            "num_sites": n_sites,
            "radius_km": round(r, 2),
            "coverage_pct": round(coverage_pct, 1),
            "total_capacity_gbps": round(total_capacity_gbps, 1),
            "capacity_per_user_mbps": round(capacity_per_user_mbps, 2),
            "capex_usd": int(capex_usd),
            "opex_annual_usd": int(opex_annual_usd),
            "avg_sinr_db": round(sinr_db, 1),
            "payback_years": round(payback_years, 1),
            "cost_per_covered_user_usd": round(capex_usd / (pop * coverage_pct / 100), 2) if coverage_pct > 0 else 0,
        }
    
    # Baseline
    baseline_metrics = calc_metrics(baseline_sites, area_km2, population, band, zone, cost_per_site)
    
    # Scénario A et B
    a_sites = baseline_sites + a_extra
    b_sites = baseline_sites + b_extra
    
    a_metrics = calc_metrics(a_sites, area_km2, population, band, zone, cost_per_site)
    b_metrics = calc_metrics(b_sites, area_km2, population, band, zone, cost_per_site)
    
    # Deltas
    def add_delta(metrics, baseline):
        m = metrics.copy()
        m["delta_sites"] = metrics["num_sites"] - baseline["num_sites"]
        m["delta_capex_usd"] = metrics["capex_usd"] - baseline["capex_usd"]
        m["delta_capacity_gbps"] = round(metrics["total_capacity_gbps"] - baseline["total_capacity_gbps"], 2)
        m["delta_coverage_pct"] = round(metrics["coverage_pct"] - baseline["coverage_pct"], 2)
        # ROI : coût marginal / capacité incrémentale
        if m["delta_capacity_gbps"] > 0:
            m["cost_per_gbps_incremental"] = int(m["delta_capex_usd"] / m["delta_capacity_gbps"])
        else:
            m["cost_per_gbps_incremental"] = 0
        return m
    
    a_final = add_delta(a_metrics, baseline_metrics)
    b_final = add_delta(b_metrics, baseline_metrics)
    
    # Recommandation
    a_roi = a_final["cost_per_gbps_incremental"]
    b_roi = b_final["cost_per_gbps_incremental"]
    
    if a_roi == 0 and b_roi == 0:
        recommendation = "Aucun gain de capacité détecté. Vérifiez les paramètres."
    elif a_roi > 0 and b_roi > 0:
        if a_roi < b_roi:
            recommendation = f"Le scénario A (+{a_extra} sites) offre le meilleur ROI : {a_roi:,} $/Gbps additionnel contre {b_roi:,} $/Gbps pour B. Chaque site ajoute en moyenne {round(a_final['delta_capacity_gbps']/a_extra, 2)} Gbps."
        else:
            recommendation = f"Le scénario B (+{b_extra} sites) offre le meilleur ROI : {b_roi:,} $/Gbps additionnel contre {a_roi:,} $/Gbps pour A. Chaque site ajoute en moyenne {round(b_final['delta_capacity_gbps']/b_extra, 2)} Gbps."
    else:
        recommendation = "Comparez les coûts marginaux pour trancher."
    
    return {
        "baseline": baseline_metrics,
        "scenario_a": a_final,
        "scenario_b": b_final,
        "recommendation": recommendation,
        "config": {
            "baseline_sites": baseline_sites,
            "a_extra_sites": a_extra,
            "b_extra_sites": b_extra,
            "band_mhz": band,
            "zone": zone,
            "cost_per_site_usd": int(cost_per_site),
            "target_area_km2": area_km2,
            "population": population,
        }
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

@app.get("/api/v1/sites")
async def get_sites():
    """
    Retourne les sites planifiés avec leurs PCI/PRACH/TAC.
    Utilisé par neighbor.html pour peupler le dropdown et la carte.
    """
    global _LAST_PLANNED_SITES
    
    if not _LAST_PLANNED_SITES:
        return {
            "sites": [],
            "count": 0,
            "message": "Aucun site planifié. Cliquez d'abord sur 'Placer les sites' dans Link Budget."
        }
    
    # Enrichir avec PCI si dispo (sinon valeur par défaut)
    sites_enriched = []
    for i, s in enumerate(_LAST_PLANNED_SITES):
        sites_enriched.append({
            "site_id": s["site_id"],
            "lat": s["lat"],
            "lon": s["lon"],
            "distance_from_center_km": s.get("distance_from_center_km", 0),
            "pci": s.get("assigned_pci", s.get("pci", i % 504)),
            "cell_id": s.get("cell_id", i + 1),
            "tac": s.get("tac", 1000),
        })
    
    return {
        "sites": sites_enriched,
        "count": len(sites_enriched)
    }
@app.post("/api/v1/terrain-import-csv")
async def import_terrain_csv(req: TerrainRequest):
    """
    Import de sites depuis une bounding box.
    Retourne les sites planifiés (_LAST_PLANNED_SITES) + les obstacles simulés.
    """
    global _LAST_PLANNED_SITES
    
    # Sites planifiés dans la bbox
    planned = []
    if _LAST_PLANNED_SITES:
        for s in _LAST_PLANNED_SITES:
            if (req.min_lat <= s["lat"] <= req.max_lat and 
                req.min_lon <= s["lon"] <= req.max_lon):
                planned.append({
                    "site_id": s["site_id"],
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "pci": s.get("assigned_pci", 0),
                    "tac": s.get("tac", 1000),
                })
    
    return {
        "planned_sites": planned,
        "count": len(planned),
        "bbox": {
            "min_lat": req.min_lat, "max_lat": req.max_lat,
            "min_lon": req.min_lon, "max_lon": req.max_lon,
        },
        "message": f"{len(planned)} sites planifiés dans cette zone"
    }
# ==========================================
# ENDPOINT 8 : SAUVEGARDE / CHARGEMENT SCÉNARIO
# ==========================================
class ScenarioSaveRequest(BaseModel):
    name: str = "scenario"
    center_lat: float = 48.4284
    center_lon: float = -71.0656

class ScenarioLoadRequest(BaseModel):
    scenario: dict

@app.post("/api/v1/scenario/save")
async def save_scenario(req: ScenarioSaveRequest):
    """
    Exporte l'état complet en JSON :
    - 98 sites avec PCI/PRACH/TAC
    - Config (fréquence, rayon, environnement)
    - Timestamp
    """
    global _LAST_PLANNED_SITES
    from datetime import datetime
    
    if not _LAST_PLANNED_SITES:
        raise HTTPException(status_code=400, detail="Aucun site en mémoire. Placez les sites d'abord.")
    
    scenario = {
        "version": "1.0",
        "name": req.name,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "center": {
            "lat": req.center_lat,
            "lon": req.center_lon,
        },
        "stats": {
            "n_sites": len(_LAST_PLANNED_SITES),
            "n_pci_unique": len(set(s.get("assigned_pci", 0) for s in _LAST_PLANNED_SITES)),
            "n_tac": len(set(s.get("tac", 1000) for s in _LAST_PLANNED_SITES)),
        },
        "sites": _LAST_PLANNED_SITES,
    }
    
    return scenario

@app.post("/api/v1/scenario/load")
async def load_scenario(req: ScenarioLoadRequest):
    """
    Recharge un scénario depuis un JSON.
    Écrase la mémoire actuelle.
    """
    global _LAST_PLANNED_SITES
    
    scenario = req.scenario
    if not scenario.get("sites"):
        raise HTTPException(status_code=400, detail="JSON invalide : champ 'sites' manquant")
    
    _LAST_PLANNED_SITES = scenario["sites"]
    
    print(f"🧠 {len(_LAST_PLANNED_SITES)} sites rechargés depuis scénario '{scenario.get('name', 'unknown')}'")
    
    return {
        "success": True,
        "n_sites": len(_LAST_PLANNED_SITES),
        "name": scenario.get("name", "unknown"),
        "saved_at": scenario.get("saved_at", "unknown"),
    }

# ==========================================
# MODULE 7 AVANCÉ : OSM RÉEL + ÉLÉVATION + LOS
# ==========================================

class TerrainImportRequest(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    mode: str = "real"  # "real" ou "demo"

class LOSRequest(BaseModel):
    site_a: str
    site_b: str

# Overpass API (OpenStreetMap)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

async def fetch_osm_buildings(bbox):
    """Récupère les bâtiments réels via Overpass API."""
    query = f"""
    [out:json][timeout:25];
    (
      way["building"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
    );
    out geom;
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(OVERPASS_URL, data={"data": query})
        r.raise_for_status()
        return r.json().get("elements", [])

async def fetch_osm_forests(bbox):
    """Récupère les forêts réelles via Overpass API."""
    query = f"""
    [out:json][timeout:25];
    (
      way["landuse"="forest"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
      way["natural"="wood"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
    );
    out geom;
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(OVERPASS_URL, data={"data": query})
        r.raise_for_status()
        return r.json().get("elements", [])

def osm_to_geojson(elements, feature_type, color, loss_db):
    """Convertit les éléments OSM en FeatureCollection GeoJSON."""
    features = []
    for el in elements:
        if el.get("type") == "way" and "geometry" in el:
            coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
            if len(coords) >= 3:
                # Fermer le polygone
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {
                        "type": feature_type,
                        "loss_db": loss_db,
                        "color": color,
                        "osm_id": el.get("id"),
                    }
                })
    return features

@app.post("/api/v1/terrain-osm-real")
async def terrain_osm_real(req: TerrainImportRequest):
    """
    Import OSM RÉEL (buildings + forests) via Overpass API.
    Fallback automatique vers le mode démo si Overpass échoue.
    """
    bbox = {
        "min_lat": req.min_lat,
        "min_lon": req.min_lon,
        "max_lat": req.max_lat,
        "max_lon": req.max_lon,
    }
    
    try:
        print(f"📡 Import OSM réel : bbox {bbox}")
        
        # Récupérer buildings + forests en parallèle
        buildings_task = fetch_osm_buildings(bbox)
        forests_task = fetch_osm_forests(bbox)
        buildings, forests = await asyncio.gather(buildings_task, forests_task)
        
        features = []
        features.extend(osm_to_geojson(buildings, "building", "#94a3b8", 15.0))
        features.extend(osm_to_geojson(forests, "forest", "#166534", 10.0))
        
        print(f"✅ OSM réel : {len(buildings)} buildings + {len(forests)} forests")
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "count": len(features),
            "mode": "real",
            "message": f"OSM réel : {len(buildings)} bâtiments + {len(forests)} forêts",
        }
    
    except Exception as e:
        print(f"⚠️ Overpass API échoué : {e} → fallback démo")
        # Fallback : mode démo
        return await import_real_terrain(TerrainRequest(**bbox))

# Open-Elevation API (élévation SRTM)
ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"

async def fetch_elevation(lat, lon):
    """Récupère l'élévation au point (lat, lon) via Open-Elevation."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                ELEVATION_URL,
                json={"locations": [{"latitude": lat, "longitude": lon}]}
            )
            r.raise_for_status()
            data = r.json()
            if data.get("results"):
                return data["results"][0].get("elevation", 0)
    except Exception as e:
        print(f"⚠️ Open-Elevation échoué pour ({lat}, {lon}): {e}")
    return 0

def haversine_km(lat1, lon1, lat2, lon2):
    """Distance Haversine en km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def fresnel_radius_m(d1_km, d2_km, freq_ghz):
    """Rayon de la 1ère zone de Fresnel au point médian (en mètres)."""
    total_km = d1_km + d2_km
    if total_km == 0 or freq_ghz <= 0:
        return 0
    # Formule : r = 17.32 * sqrt((d1*d2)/(f*total)) en mètres
    return 17.32 * math.sqrt((d1_km * d2_km) / (freq_ghz * total_km))

@app.post("/api/v1/los-analysis")
async def los_analysis(req: LOSRequest):
    """
    Analyse LOS entre 2 sites avec profil d'élévation + Fresnel.
    """
    global _LAST_PLANNED_SITES
    
    if not _LAST_PLANNED_SITES:
        raise HTTPException(status_code=400, detail="Aucun site en mémoire")
    
    site_a = next((s for s in _LAST_PLANNED_SITES if s["site_id"] == req.site_a), None)
    site_b = next((s for s in _LAST_PLANNED_SITES if s["site_id"] == req.site_b), None)
    
    if not site_a or not site_b:
        raise HTTPException(status_code=404, detail="Site non trouvé")
    
    dist_km = haversine_km(site_a["lat"], site_a["lon"], site_b["lat"], site_b["lon"])
    
    # Récupérer élévations : A, milieu, B
    elevations = await asyncio.gather(
        fetch_elevation(site_a["lat"], site_a["lon"]),
        fetch_elevation((site_a["lat"] + site_b["lat"]) / 2, (site_a["lon"] + site_b["lon"]) / 2),
        fetch_elevation(site_b["lat"], site_b["lon"]),
    )
    elev_a, elev_mid, elev_b = elevations
    
    # Hauteurs antenne : hauteur terrain + hauteur pylône
    hauteur_pylone = 30  # m (par défaut)
    ant_a = elev_a + hauteur_pylone
    ant_b = elev_b + hauteur_pylone
    
    # Ligne directe au milieu
    ligne_directe = (ant_a + ant_b) / 2
    
    # Fresnel radius (freq 3.5 GHz)
    fresnel_m = fresnel_radius_m(dist_km / 2, dist_km / 2, 3.5)
    
    # Obstruction : terrain > ligne directe - fresnel 60%
    clearance = ligne_directe - elev_mid
    los_ok = clearance > (0.6 * fresnel_m)
    
    return {
        "site_a": {
            "id": site_a["site_id"],
            "lat": site_a["lat"],
            "lon": site_a["lon"],
            "elevation_m": elev_a,
            "antenna_m": ant_a
        },
        "site_b": {
            "id": site_b["site_id"],
            "lat": site_b["lat"],
            "lon": site_b["lon"],
            "elevation_m": elev_b,
            "antenna_m": ant_b
        },
        "distance_km": round(dist_km, 3),
        "elevation_mid_m": elev_mid,
        "line_of_sight_m": round(ligne_directe, 1),
        "clearance_m": round(clearance, 1),
        "fresnel_radius_m": round(fresnel_m, 1),
        "los_ok": los_ok,
        "status": "✅ LOS OK" if los_ok else "❌ Obstrué",
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "RF Planner API is running"}

@app.get("/api/v1/memory-status")
def memory_status():
    """Debug : nombre de sites en mémoire"""
    return {
        "planned_sites_in_memory": len(_LAST_PLANNED_SITES),
        "mode": "real" if _LAST_PLANNED_SITES else "mock"
    }