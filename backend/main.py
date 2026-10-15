import sys
import os
sys.path.append(os.path.dirname(__file__))
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models import *
from database import engine, get_db
from rf_calculations import calculate_link_budget, estimate_sites_needed
from hexagon_grid import generate_hexagon_grid
import math

# Créer les tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RF Planner API",
    description="Backend pour la planification RF pré-déploiement",
    version="1.0.0"
)

# CORS (pour le frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod, restreindre à votre domaine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# ENDPOINT 1: Link Budget Calculator
# ==========================================
@app.post("/api/v1/link-budget", response_model=LinkBudgetResponse)
async def calculate_link_budget_endpoint(request: LinkBudgetRequest):
    try:
        # Calcul RF
        mapl, radius_km = calculate_link_budget(
            request.frequency_mhz,
            request.antenna_height_m,
            request.clutter_loss_db,
            request.propagation_model
        )
        
        # Estimation du nombre de sites
        estimated_sites = estimate_sites_needed(
            request.target_area_km2,
            radius_km
        )
        
        # Génération de la grille hexagonale
        num_rings = min(3, max(1, math.ceil(math.sqrt(estimated_sites) / 3)))
        hexagons_geojson = generate_hexagon_grid(
            request.center_lat,
            request.center_lon,
            radius_km,
            num_rings=num_rings
        )
        
        return LinkBudgetResponse(
            mapl_db=mapl,
            radius_km=radius_km,
            estimated_sites=estimated_sites,
            hexagons_geojson=hexagons_geojson
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de calcul: {str(e)}")

# ==========================================
# ENDPOINT 2: Création de Projet
# ==========================================
@app.post("/api/v1/projects")
async def create_project(project: Project, db: Session = Depends(get_db)):
    db_project = Project(**project.dict())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return {"id": str(db_project.id), "message": "Projet créé"}

# ==========================================
# ENDPOINT 3: Ajout de Site
# ==========================================
@app.post("/api/v1/sites")
async def add_site(site: Site, db: Session = Depends(get_db)):
    db_site = Site(**site.dict())
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return {"id": str(db_site.id), "message": "Site ajouté"}

# ==========================================
# ENDPOINT 4: Planification de Voisinage
# ==========================================
@app.post("/api/v1/neighbors", response_model=NeighborResponse)
async def plan_neighbors(request: NeighborRequest, db: Session = Depends(get_db)):
    # Logique de détection de voisins (à implémenter avec PostGIS)
    # Pour l'instant, retourne un exemple
    return NeighborResponse(
        neighbors=[
            {"site_id": "GNB_004", "distance_m": 1200, "azimuth": 120},
            {"site_id": "GNB_007", "distance_m": 800, "azimuth": 240}
        ],
        vendor_script="ADD GNBRELATION: LocalCellId=1, NrNeighborCellId=4, NrPci=125, Switch=ON;"
    )

@app.get("/")
def read_root():
    return {"message": "RF Planner API is running"}

from neighbor_planner import MOCK_PROJECT_SITES, detect_neighbors, generate_vendor_script
from pydantic import BaseModel

class NeighborRequest(BaseModel):
    source_site_id: str
    detection_radius_m: float = 2000.0
    vendor: str = "Huawei" # Huawei, Ericsson, Nokia, Samsung

class NeighborResponse(BaseModel):
    source_site: dict
    neighbors: list
    vendor_script: str

@app.post("/api/v1/neighbors", response_model=NeighborResponse)
async def plan_neighbors(request: NeighborRequest):
    # 1. Trouver le site source
    source_site = next((s for s in MOCK_PROJECT_SITES if s["site_id"] == request.source_site_id), None)
    if not source_site:
        raise HTTPException(status_code=404, detail="Site source non trouvé")
    
    # 2. Détecter les voisins
    neighbors = detect_neighbors(source_site, MOCK_PROJECT_SITES, request.detection_radius_m)
    
    # 3. Générer le script
    script = generate_vendor_script(source_site, neighbors, request.vendor)
    
    return {
        "source_site": source_site,
        "neighbors": neighbors,
        "vendor_script": script
    }

from pci_planner import assign_pcis_5gnr, assign_prach_and_tac, generate_pci_scripts
# Assurez-vous d'avoir une structure de voisins, ici simulée
MOCK_NEIGHBORS = {
    "MTL_5G_001": ["MTL_5G_002", "MTL_5G_003"],
    "MTL_5G_002": ["MTL_5G_001", "MTL_5G_004"],
    "MTL_5G_003": ["MTL_5G_001", "MTL_5G_005"],
    "MTL_5G_004": ["MTL_5G_002"],
    "MTL_5G_005": ["MTL_5G_003"]
}

class PCIPlanningRequest(BaseModel):
    vendor: str = "Huawei"
    enforce_mod3: bool = True
    enforce_mod30: bool = True

@app.post("/api/v1/pci-planning")
async def run_pci_planning(request: PCIPlanningRequest):
    # 1. Récupérer les sites (depuis la DB ou MOCK)
    sites = MOCK_PROJECT_SITES.copy() # Utiliser la liste du module précédent
    
    # 2. Lancer l'algorithme
    sites = assign_pcis_5gnr(sites, MOCK_NEIGHBORS)
    sites = assign_prach_and_tac(sites)
    
    # 3. Générer les scripts
    script = generate_pci_scripts(sites, request.vendor)
    
    # 4. Calculer les conflits résiduels (pour l'UI)
    conflicts = []
    for site in sites:
        for n_id in MOCK_NEIGHBORS.get(site["site_id"], []):
            neighbor = next((s for s in sites if s["site_id"] == n_id), None)
            if neighbor and (site["assigned_pci"] % 3 == neighbor["assigned_pci"] % 3):
                conflicts.append(f"{site['site_id']} <-> {n_id} (Mod-3)")

    return {
        "sites": sites,
        "script": script,
        "conflicts": conflicts,
        "stats": {
            "total_sites": len(sites),
            "unique_pcis": len(set(s["assigned_pci"] for s in sites)),
            "tacs_used": len(set(s["tac"] for s in sites))
        }
    }