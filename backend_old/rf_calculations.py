import math

def calculate_link_budget(
    frequency_mhz: float,
    antenna_height_m: float,
    clutter_loss_db: float,
    propagation_model: str
) -> tuple[float, float]:
    """
    Calcule le MAPL et le rayon de cellule estimé.
    Retourne: (mapl_db, radius_km)
    """
    # Paramètres de base
    tx_power_dbm = 43.0  # 20W
    rx_sensitivity_dbm = -95.0
    feeder_loss_db = 2.0
    body_loss_db = 1.0
    margin_fading_db = 8.0
    
    # Gain d'antenne (simplifié)
    antenna_gain_dbi = 16.0 if frequency_mhz < 2000 else 18.0
    
    # MAPL de base
    base_mapl = (tx_power_dbm + antenna_gain_dbi 
                 - rx_sensitivity_dbm - feeder_loss_db 
                 - body_loss_db - margin_fading_db)
    
    # Calcul du rayon selon le modèle
    if propagation_model == "cost231":
        # Urbain dense
        path_loss_factor = 38.0 + 20 * math.log10(frequency_mhz)
        radius_km = max(0.2, (base_mapl - clutter_loss_db - 20) / path_loss_factor * 1.5)
    elif propagation_model == "hata":
        # Suburbain/Rural
        path_loss_factor = 28.0 + 20 * math.log10(frequency_mhz)
        radius_km = max(0.5, (base_mapl - clutter_loss_db - 10) / path_loss_factor * 2.0)
    elif propagation_model == "itu2108":
        # 5G mmWave
        radius_km = max(0.1, (base_mapl - clutter_loss_db - 40) / (20 * math.log10(frequency_mhz)) * 0.5)
    else:
        radius_km = 1.0  # Défaut
    
    final_mapl = base_mapl - clutter_loss_db
    return round(final_mapl, 1), round(radius_km, 2)

def estimate_sites_needed(target_area_km2: float, radius_km: float) -> int:
    """
    Estime le nombre de sites nécessaires pour couvrir une zone.
    Formule: surface_hexagone = 3*sqrt(3)/2 * r^2
    """
    hex_area_km2 = (3 * math.sqrt(3) / 2) * (radius_km ** 2)
    effective_area_per_site = hex_area_km2 * 0.65  # Facteur de recouvrement
    return math.ceil(target_area_km2 / effective_area_per_site)