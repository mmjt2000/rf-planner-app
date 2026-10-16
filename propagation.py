# Copyright (c) 2026 Jean Thomas Montezuma Montreuil
# All Rights Reserved.

"""
Modeles de propagation RF pour RF Planner
- Friis (reference)
- Okumura-Hata (150-1500 MHz)
- COST-231 Hata (1500-2000 MHz)
- COST-231 Walfisch-Ikegami (> 2000 MHz)
- ITU-R P.1546 (rural/suburbain)
- ITU-R P.2108 (5G mmWave)

Sources: ITU-R recommendations, 3GPP TR 38.901, COST-231
"""
import math


# ============================================================
# CONSTANTES
# ============================================================
C = 3e8  # Vitesse lumiere (m/s)


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================
def dbm_to_w(dbm):
    """Conversion dBm vers Watt"""
    return 10 ** ((dbm - 30) / 10)


def w_to_dbm(w):
    """Conversion Watt vers dBm"""
    if w <= 0:
        return -math.inf
    return 10 * math.log10(w) + 30


def fspl(freq_mhz, distance_km):
    """
    Free Space Path Loss (Friis)
    L = 32.44 + 20*log10(f_MHz) + 20*log10(d_km)
    """
    if distance_km <= 0 or freq_mhz <= 0:
        return 0
    return 32.44 + 20 * math.log10(freq_mhz) + 20 * math.log10(distance_km)


# ============================================================
# OKUMURA-HATA (150 - 1500 MHz)
# ============================================================
def okumura_hata(freq_mhz, hb_m, hm_m, d_km, environment="urban"):
    """
    Modele Okumura-Hata (150-1500 MHz)
    
    Args:
        freq_mhz : frequence en MHz (150-1500)
        hb_m     : hauteur antenne base (30-200 m)
        hm_m     : hauteur mobile (1-10 m)
        d_km     : distance en km (1-20)
        environment : urban, suburban, rural
    
    Returns:
        Path loss en dB
    """
    if freq_mhz < 150 or freq_mhz > 1500:
        # Utiliser COST-231 pour etendre la plage
        pass
    
    # Facteur de correction antenne mobile
    if freq_mhz <= 200:
        a_hm = 8.29 * (math.log10(1.54 * hm_m)) ** 2 - 1.1
    elif freq_mhz <= 400:
        a_hm = 3.2 * (math.log10(11.75 * hm_m)) ** 2 - 4.97
    else:
        a_hm = 3.2 * (math.log10(11.75 * hm_m)) ** 2 - 4.97
    
    # Path loss urbain de base
    L_urban = (
        69.55
        + 26.16 * math.log10(freq_mhz)
        - 13.82 * math.log10(hb_m)
        - a_hm
        + (44.9 - 6.55 * math.log10(hb_m)) * math.log10(d_km)
    )
    
    # Corrections selon environnement
    if environment == "suburban":
        L_suburban = L_urban - 2 * (math.log10(freq_mhz / 28)) ** 2 - 5.4
        return L_suburban
    elif environment == "rural":
        L_rural = L_urban - 4.78 * (math.log10(freq_mhz)) ** 2 + 18.33 * math.log10(freq_mhz) - 40.94
        return L_rural
    else:  # urban
        return L_urban


# ============================================================
# COST-231 HATA (1500 - 2000 MHz)
# ============================================================
def cost231_hata(freq_mhz, hb_m, hm_m, d_km, environment="urban"):
    """
    Modele COST-231 Hata (1500-2000 MHz)
    Extension d'Okumura-Hata pour frequences plus hautes
    """
    # Facteur de correction antenne mobile
    a_hm = 3.2 * (math.log10(11.75 * hm_m)) ** 2 - 4.97
    
    # Correction environnement (Cm)
    if environment == "urban":
        Cm = 3.0  # Ville de taille moyenne
    elif environment == "dense_urban":
        Cm = 0.0  # Centre-ville
    elif environment == "suburban":
        Cm = -2 * (math.log10(freq_mhz / 28)) ** 2 - 5.4
    else:  # rural
        Cm = 0.0
    
    L = (
        46.3
        + 33.9 * math.log10(freq_mhz)
        - 13.82 * math.log10(hb_m)
        - a_hm
        + (44.9 - 6.55 * math.log10(hb_m)) * math.log10(d_km)
        + Cm
    )
    return L


# ============================================================
# COST-231 WALFISCH-IKEGAMI (> 2000 MHz)
# ============================================================
def cost231_walfisch_ikegami(
    freq_mhz, hb_m, hm_m, d_km,
    building_height_m=15.0, street_width_m=20.0, building_separation_m=40.0,
    street_orientation_deg=90.0
):
    """
    Modele COST-231 Walfisch-Ikegami (pour 800-2000+ MHz)
    Recommande pour zones urbaines denses
    
    Args:
        building_height_m : hauteur moyenne batiments (m)
        street_width_m    : largeur rue (m)
        building_separation_m : distance entre batiments (m)
        street_orientation_deg : orientation rue (degres)
    """
    # Hauteur mobile effective
    dh = hb_m - building_height_m
    if dh < 0:
        dh = 0
    
    # Free Space Loss
    Lfs = 32.44 + 20 * math.log10(freq_mhz) + 20 * math.log10(d_km)
    
    # Roof-top to street diffraction
    Lrts = -16.9 - 10 * math.log10(street_width_m) + 10 * math.log10(freq_mhz) + 20 * math.log10(dh)
    
    # Multiscreen diffraction
    Lms = (
        -6.55
        + 20 * math.log10(freq_mhz)
        + 10 * math.log10(d_km * 1000)
        - 13.82 * math.log10(hb_m)
        - 10 * math.log10(building_separation_m)
    )
    
    # Correction orientation
    if street_orientation_deg < 35:
        Lori = -10 + 0.354 * street_orientation_deg
    elif street_orientation_deg < 55:
        Lori = 2.5 + 0.075 * (street_orientation_deg - 35)
    else:
        Lori = 4.0 - 0.114 * (street_orientation_deg - 55)
    
    # Si hb est bas, on utilise seulement Lfs (LOS)
    if Lms < 0 and dh > 0:
        # Cas ou on est en dessous des batiments
        L = Lfs + Lrts + Lms
    else:
        L = Lfs + Lrts + Lms
    
    if L < Lfs:
        L = Lfs
    
    return L


# ============================================================
# ITU-R P.1546 (rural/suburbain - 30-3000 MHz)
# ============================================================
def itu_r_p1546(freq_mhz, hb_m, hm_m, d_km, environment="rural"):
    """
    Modele ITU-R P.1546 (version simplifiee)
    Reference pour radiodiffusion et mobile
    """
    # Hauteur effective
    h_eff = hb_m - 10  # Approximation
    
    # Courbe de base (simplifiee)
    E = 30 + 20 * math.log10(freq_mhz) - 20 * math.log10(d_km)  # Champ en dBuV/m
    
    # Ajustement selon environnement
    if environment == "rural":
        delta = 0
    elif environment == "suburban":
        delta = -6
    elif environment == "urban":
        delta = -12
    else:
        delta = 0
    
    # Conversion en path loss
    # L = 20*log10(f) + 20*log10(d) + 32.44 - Gt - Gr + correction
    L = fspl(freq_mhz, d_km) + delta
    
    return L


# ============================================================
# ITU-R P.2108 (mmWave - 5G)
# ============================================================
def itu_r_p2108(freq_mhz, d_km, clutter="urban"):
    """
    Modele ITU-R P.2108 pour 5G mmWave
    Pertes supplementaires (batiments, pluie, vegetation)
    """
    # Pertes batiments (approximation)
    # A = alpha * d^beta * f^gamma
    if clutter == "urban":
        alpha, beta, gamma = 0.5, 0.7, 0.3
    elif clutter == "suburban":
        alpha, beta, gamma = 0.3, 0.6, 0.2
    else:  # rural
        alpha, beta, gamma = 0.1, 0.5, 0.1
    
    # Pertes additionnelles au-dessus du FSPL
    L_clutter = alpha * (d_km ** beta) * ((freq_mhz / 1000) ** gamma) * 10
    
    Lfs = fspl(freq_mhz, d_km)
    return Lfs + L_clutter


# ============================================================
# CALCUL MAPL (Maximum Allowable Path Loss)
# ============================================================
def calculate_mapl(
    tx_power_dbm=43.0,
    tx_antenna_gain_dbi=18.0,
    tx_cable_loss_db=2.0,
    rx_antenna_gain_dbi=0.0,
    rx_cable_loss_db=0.0,
    rx_sensitivity_dbm=-95.0,
    interference_margin_db=3.0,
    shadowing_margin_db=8.0,
    body_loss_db=0.0,
    eirp_offset_db=0.0
):
    """
    Calcul du MAPL (Maximum Allowable Path Loss)
    
    MAPL = EIRP - Sensibilite + Gains - Marges - Pertes
    """
    # EIRP = Puissance TX + Gain antenne TX - Pertes cable
    eirp_dbm = tx_power_dbm + tx_antenna_gain_dbi - tx_cable_loss_db + eirp_offset_db
    
    # Path loss maximal
    mapl = (
        eirp_dbm
        - rx_sensitivity_dbm
        + rx_antenna_gain_dbi
        - rx_cable_loss_db
        - interference_margin_db
        - shadowing_margin_db
        - body_loss_db
    )
    
    return {
        "eirp_dbm": round(eirp_dbm, 2),
        "mapl_db": round(mapl, 2),
        "tx_power_dbm": tx_power_dbm,
        "tx_antenna_gain_dbi": tx_antenna_gain_dbi,
        "rx_sensitivity_dbm": rx_sensitivity_dbm,
        "margins_db": interference_margin_db + shadowing_margin_db + body_loss_db,
    }


# ============================================================
# CALCUL RAYON DE CELLULE (inversion)
# ============================================================
def calculate_radius_km(
    mapl_db,
    freq_mhz,
    hb_m=30.0,
    hm_m=1.5,
    model="cost231_hata",
    environment="suburban",
    **kwargs
):
    """
    Calcule le rayon de cellule en inversant le modele de propagation.
    Utilise une recherche binaire sur la distance.
    """
    # Bornes initiales
    d_min = 0.01  # 10 m
    d_max = 50.0   # 50 km
    
    # Fonction de calcul du path loss selon modele
    def path_loss(d):
        if model == "okumura_hata":
            return okumura_hata(freq_mhz, hb_m, hm_m, d, environment)
        elif model == "cost231_hata":
            return cost231_hata(freq_mhz, hb_m, hm_m, d, environment)
        elif model == "cost231_wi":
            return cost231_walfisch_ikegami(freq_mhz, hb_m, hm_m, d, **kwargs)
        elif model == "itu_r_p1546":
            return itu_r_p1546(freq_mhz, hb_m, hm_m, d, environment)
        elif model == "itu_r_p2108":
            return itu_r_p2108(freq_mhz, d, environment)
        elif model == "fspl":
            return fspl(freq_mhz, d)
        else:
            return cost231_hata(freq_mhz, hb_m, hm_m, d, environment)
    
    # Verifier que le path loss augmente avec la distance
    if path_loss(d_min) > mapl_db:
        return d_min  # Meme a 10m, on depasse le MAPL
    
    if path_loss(d_max) < mapl_db:
        return d_max  # Meme a 50km, on n'atteint pas le MAPL
    
    # Recherche binaire
    for _ in range(50):
        d_mid = (d_min + d_max) / 2
        L_mid = path_loss(d_mid)
        
        if L_mid < mapl_db:
            d_min = d_mid
        else:
            d_max = d_mid
        
        if abs(d_max - d_min) < 0.001:
            break
    
    return round((d_min + d_max) / 2, 3)


# ============================================================
# ESTIMATION NOMBRE DE SITES (grille hexagonale)
# ============================================================
def estimate_sites_hexagonal(target_area_km2, radius_km, overlap_factor=0.65):
    """
    Estime le nombre de sites necessaires pour couvrir une zone
    en utilisant une grille hexagonale (modele 3-secteurs).
    
    Args:
        target_area_km2 : surface a couvrir
        radius_km       : rayon de cellule
        overlap_factor  : facteur d'efficacite (0.5-0.8)
    
    Returns:
        Nombre de sites estimes + aire hexagone
    """
    if radius_km <= 0:
        return {"sites": 0, "hex_area_km2": 0}
    
    # Aire d'un hexagone avec R = rayon
    # A = (3 * sqrt(3) / 2) * R^2
    hex_area = (3 * math.sqrt(3) / 2) * (radius_km ** 2)
    
    # Nombre de sites (avec facteur d'efficacite)
    effective_area = hex_area * overlap_factor
    sites = math.ceil(target_area_km2 / effective_area)
    
    return {
        "sites": sites,
        "hex_area_km2": round(hex_area, 2),
        "effective_area_km2": round(effective_area, 2),
    }


# ============================================================
# SELECTION AUTO DU MODELE
# ============================================================
def select_best_model(freq_mhz, environment="suburban"):
    """
    Selectionne le meilleur modele selon la frequence et l'environnement.
    """
    if freq_mhz >= 24000:  # mmWave 24+ GHz
        return "itu_r_p2108"
    elif freq_mhz > 2000:  # 2-24 GHz (5G sub-6, WiFi 6)
        if environment == "urban" or environment == "dense_urban":
            return "cost231_wi"
        else:
            return "cost231_hata"
    elif freq_mhz > 1500:  # 1.5-2 GHz (LTE 1800, 2100)
        return "cost231_hata"
    elif freq_mhz >= 150:  # 150 MHz - 1.5 GHz (2G, 3G, 700-900 MHz)
        return "okumura_hata"
    else:
        return "fspl"
