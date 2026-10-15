import math
from typing import List, Dict, Tuple

# ==========================================
# 1. LOGIQUE D'ATTRIBUTION PCI (Graph Coloring)
# ==========================================
def assign_pcis_5gnr(sites: List[Dict], neighbors_map: Dict[str, List[str]]) -> List[Dict]:
    """
    Attribue les PCI (0-1007 pour 5G NR) en évitant les conflits Mod-3 et Mod-30.
    neighbors_map: {"SITE_A": ["SITE_B", "SITE_C"], ...}
    """
    # Trier les sites par degré (nombre de voisins) décroissant (Heuristique DSatur)
    sorted_sites = sorted(sites, key=lambda s: len(neighbors_map.get(s["site_id"], [])), reverse=True)
    
    assigned_pcis = {}
    
    for site in sorted_sites:
        site_id = site["site_id"]
        used_mod3 = set()
        used_mod30 = set()
        
        # 1. Récupérer les contraintes des voisins directs (1-hop) -> Conflit Mod-3 & Mod-30
        for neighbor_id in neighbors_map.get(site_id, []):
            if neighbor_id in assigned_pcis:
                pci = assigned_pcis[neighbor_id]
                used_mod3.add(pci % 3)
                used_mod30.add(pci % 30)
                
        # 2. Récupérer les contraintes des voisins indirects (2-hop) -> Conflit Mod-30 uniquement
        for neighbor_id in neighbors_map.get(site_id, []):
            for indirect_neighbor_id in neighbors_map.get(neighbor_id, []):
                if indirect_neighbor_id in assigned_pcis and indirect_neighbor_id != site_id:
                    pci = assigned_pcis[indirect_neighbor_id]
                    used_mod30.add(pci % 30)

        # 3. Trouver le plus petit PCI disponible (0 à 1007)
        selected_pci = -1
        for pci in range(1008):
            if (pci % 3) not in used_mod3 and (pci % 30) not in used_mod30:
                selected_pci = pci
                break
                
        if selected_pci == -1:
            selected_pci = 0 # Fallback si saturation (ne devrait pas arriver avec 1008 PCI)
            
        assigned_pcis[site_id] = selected_pci
        site["assigned_pci"] = selected_pci
        
    return sites

# ==========================================
# 2. ATTRIBUTION PRACH & TAC
# ==========================================
def assign_prach_and_tac(sites: List[Dict]) -> List[Dict]:
    """
    PRACH Root Sequence : basé sur le PCI pour garantir une réutilisation spatiale.
    TAC : Attribution par cluster géographique (simplifié par quadrillage pour la démo).
    """
    for site in sites:
        # PRACH Root Sequence Index (0-837 pour LTE, adapté pour 5G NR)
        # Formule simple : (PCI * 7) % 838 pour bien disperser les séquences
        site["prach_root"] = (site["assigned_pci"] * 7) % 838
        
        # TAC (Tracking Area Code) : regroupement par zone (ex: modulo sur la latitude/longitude)
        # Pour la démo, on crée des TAC de 10 sites
        site_index = sites.index(site)
        site["tac"] = 1000 + (site_index // 10) 
        
    return sites

# ==========================================
# 3. GÉNÉRATION DE SCRIPTS MULTI-VENDOR (Mise à jour PCI)
# ==========================================
def generate_pci_scripts(sites: List[Dict], vendor: str) -> str:
    script_lines = [f"# RF Planner - PCI/PRACH/TAC Auto-Configuration", f"# Vendor: {vendor}", "-" * 40]
    
    for site in sites:
        cell_id = site["cell_id"]
        pci = site["assigned_pci"]
        prach = site["prach_root"]
        tac = site["tac"]
        
        if vendor == "Huawei":
            script_lines.append(f"MOD NRCELL: LocalCellId={cell_id}, PhyCellId={pci}, Tac={tac};")
            script_lines.append(f"MOD NRPRACH: LocalCellId={cell_id}, RootSequenceIndex={prach};")
        elif vendor == "Ericsson":
            script_lines.append(f"nrpci set LocalCellId={cell_id} Pci={pci} Tac={tac};")
            script_lines.append(f"nrprach set LocalCellId={cell_id} RootSequenceIndex={prach};")
        elif vendor == "Nokia":
            script_lines.append(f"SET NRCELL: LOCALCELLID={cell_id}, PHYCELLID={pci}, TAC={tac};")
            
    return "\n".join(script_lines)