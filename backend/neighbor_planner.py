import math
from typing import List, Dict
from shapely.geometry import Point

# ==========================================
# 1. BASE DE DONNÉES SIMULÉE (À remplacer par votre DB Neon)
# ==========================================
# Format : { "site_id": "...", "lat": ..., "lon": ..., "pci": ..., "cell_id": ... }
MOCK_PROJECT_SITES = [
    {"site_id": "MTL_5G_001", "lat": 48.4284, "lon": -71.0656, "pci": 10, "cell_id": 1},
    {"site_id": "MTL_5G_002", "lat": 48.4350, "lon": -71.0550, "pci": 11, "cell_id": 2},
    {"site_id": "MTL_5G_003", "lat": 48.4200, "lon": -71.0750, "pci": 13, "cell_id": 3}, # Conflit Mod-3 avec 001 (10 et 13)
    {"site_id": "MTL_5G_004", "lat": 48.4400, "lon": -71.0800, "pci": 14, "cell_id": 4},
    {"site_id": "MTL_5G_005", "lat": 48.4150, "lon": -71.0500, "pci": 20, "cell_id": 5},
]

# ==========================================
# 2. LOGIQUE GÉOSPATIALE (Shapely / Math)
# ==========================================
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en mètres entre deux points GPS."""
    R = 6371000  # Rayon de la Terre en mètres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def detect_neighbors(source_site: Dict, all_sites: List[Dict], radius_m: float) -> List[Dict]:
    """Détecte les voisins dans un rayon donné et vérifie les conflits PCI (Mod-3)."""
    neighbors = []
    source_point = Point(source_site["lon"], source_site["lat"])
    
    for site in all_sites:
        if site["site_id"] == source_site["site_id"]:
            continue # Ignorer le site source
            
        dist = haversine_distance(source_site["lat"], source_site["lon"], site["lat"], site["lon"])
        
        if dist <= radius_m:
            # Vérification de conflit Mod-3 (Règle d'or en LTE/5G pour éviter l'interférence PSS)
            pci_conflict = (source_site["pci"] % 3) == (site["pci"] % 3)
            
            neighbors.append({
                "site_id": site["site_id"],
                "distance_m": round(dist, 1),
                "pci": site["pci"],
                "cell_id": site["cell_id"],
                "pci_conflict_mod3": pci_conflict
            })
            
    # Trier par distance croissante
    return sorted(neighbors, key=lambda x: x["distance_m"])

# ==========================================
# 3. GÉNÉRATEUR DE SCRIPTS MULTI-VENDOR
# ==========================================
def generate_vendor_script(source_site: Dict, neighbors: List[Dict], vendor: str) -> str:
    """Génère le script d'ajout de voisins selon le constructeur."""
    script_lines = []
    script_lines.append(f"# RF Planner Auto-Generated Script")
    script_lines.append(f"# Source Site: {source_site['site_id']} (Cell ID: {source_site['cell_id']}, PCI: {source_site['pci']})")
    script_lines.append(f"# Vendor: {vendor} | Neighbors: {len(neighbors)}")
    script_lines.append("-" * 40)
    
    local_cell_id = source_site["cell_id"]
    
    for n in neighbors:
        neighbor_cell_id = n["cell_id"]
        pci = n["pci"]
        
        if vendor == "Huawei":
            # Format MML Huawei 5G NR
            script_lines.append(f"ADD GNBRELATION: LocalCellId={local_cell_id}, NrNeighborCellId={neighbor_cell_id}, NrPci={pci}, Switch=ON, HoSwitch=ON;")
            
        elif vendor == "Ericsson":
            # Format Moshell / AMOS Ericsson 5G NR
            script_lines.append(f"nrrelation add LocalCellId={local_cell_id} NeighborCellId={neighbor_cell_id} Pci={pci} HoAllowed=Yes;")
            
        elif vendor == "Nokia":
            # Format CLI / ZEEI Nokia 5G NR
            script_lines.append(f"ADD NRCELLNBR: LOCALCELLID={local_cell_id}, NEIGHBOURCELLID={neighbor_cell_id}, PCI={pci}, SWITCH=ON;")
            
        elif vendor == "Samsung":
            # Format CLI Samsung
            script_lines.append(f"addNrNeighborCell --localCellId {local_cell_id} --neighborCellId {neighbor_cell_id} --pci {pci} --hoAllowed true")
            
        else:
            script_lines.append(f"# Vendor {vendor} non supporté pour l'export automatique.")
            
    return "\n".join(script_lines)