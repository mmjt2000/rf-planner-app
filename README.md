# RF Planner — Pre-Deployment Design Tool

> **Statut** : 🚧 Spécification fonctionnelle terminée · Code à venir
> 
> **Phase** : Conception

Outil de **design et planification RF** pour le RF Planner / Architecte réseau.
Complète l'écosystème d'outils RF existants en couvrant la phase **avant déploiement**
(conception, dimensionnement, planification d'identifiants).

## Positionnement dans l'écosystème RF

| Phase | Outil | Utilisateur cible |
|---|---|---|
| **1. Conception** | **RF Planner** *(ce projet)* | RF Planner / Architecte |
| 2. Intégration | RF Engineering 2.0 | Ingénieur NOC |
| 3. Analyse | RF Analytics | Manager RF |
| 4. Terrain | RF Optimizer Tools | Technicien / Field Engineer |

## Modules prévus

### 1. Estimation de couverture & Link Budget
- Tracer une zone cible sur carte (Leaflet)
- Saisir les paramètres marketing (population, type de zone, technos)
- Calcul automatique : sites requis = max(capacity, coverage)
- Suggestions de placement (grille hexagonale)

### 2. Link Budget Calculator
- Distance théorique par techno
- Modèles de propagation :
  - **Urbain dense** : ITU-R P.1411 ou COST-231 Walfisch-Ikegami
  - **Suburbain / Rural** : ITU-R P.1546 ou Okumura-Hata
  - **5G mmWave** : ITU-R P.2108 (pertes bâtiments / pluie)
- Sortie : MAPL, rayon cellule, nombre de sites

### 3. Placement des sites
- Grille hexagonale automatique
- Placement manuel ajustable
- Détection trous / overlap
- Librairies : `GeoPandas`, `Shapely`

### 4. Planification de voisinage
- Auto-détection des voisins (rayon paramétrable)
- Calcul de distance entre sites
- Export scripts multi-vendor :
  - **Huawei** : `ADD GNBRELATION`
  - **Ericsson** : `nrrelation`
  - **Nokia** : `ZEEI` script
  - **Samsung** : CLI script

### 5. PCI / PRACH / TAC Planning
- Attribution sans conflit (mod-3, mod-30)
- Vérification de conflits géographiques
- Export scripts vendor

### 6. Nominal Planning
- Paramètres initiaux par site (azimuth, tilt, puissance, mobilité)
- Recommandations selon type de zone
- Export "Nominal Plan" complet

### 7. Simulateur de scénarios
- Comparer configurations (ex: 15 vs 25 sites)
- Analyse coût vs couverture vs capacité
- Export PDF pour la direction

### 8. Import terrain réel
- **Relief (SRTM)** : Copernicus DEM (30m) ou NASA SRTM
- **Clutter (occupation des sols)** : OpenStreetMap (Overpass API) ou Corine Land Cover
- Import sites existants
- Analyse avec obstacles

## Stack technique prévue

| Couche | Technologie |
|---|---|
| **Backend** | FastAPI + PostgreSQL + GeoPandas + Shapely |
| **Frontend** | HTML/CSS/JS + Leaflet + Chart.js + Mapbox GL JS |
| **Auth** | JWT (réutiliser depuis RF Analytics) |
| **Multi-tenant** | 1 tenant = 1 opérateur = 1 projet |
| **Déploiement** | Render + Neon |
| **IA** | RF Planner Copilot (Groq — réutiliser de RF Analytics) |

## Cas d'usage concret

**Scénario** : Digicel veut couvrir Chicoutimi en 5G.

1. Import démographique : 150 000 habitants à couvrir
2. Link budget : bande 3.5 GHz, radius ~500m en urbain
3. Estimation : ~30 sites nécessaires
4. Placement : grille hexagonale + ajustement manuel
5. Voisinage : génération automatique des relations
6. PCI / PRACH : attribution sans conflit
7. Nominal plan : paramètres initiaux par site
8. Export : scripts Huawei MML prêts pour intégration
9. Simulation : "si on n'a que 20 sites, quel % de couverture ?"

**Résultat** : plan complet en 1 journée au lieu de 2 semaines.

## Roadmap

- [ ] Module 1 : Estimation couverture & Link Budget
- [ ] Module 2 : Link Budget Calculator
- [ ] Module 3 : Placement des sites
- [ ] Module 4 : Planification de voisinage
- [ ] Module 5 : PCI / PRACH / TAC Planning
- [ ] Module 6 : Nominal Planning
- [ ] Module 7 : Simulateur de scénarios
- [ ] Module 8 : Import terrain réel

## Auteur

**Jean Thomas Montezuma Montreuil**
Ingénieur Radiofréquence Senior · 15+ ans d'expérience
Portfolio : https://mon-site-rf.onrender.com
LinkedIn : https://www.linkedin.com/in/jean-thomas-montezuma-montreuil-383aa813/

## License

All Rights Reserved © 2026