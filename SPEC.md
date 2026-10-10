# RF Planner — Spécification Fonctionnelle Complète

## Récap

**Projet** : rf-planner-app
**Statut** : Spécification terminée · Code à venir
**Position** : Couvre la phase **Conception** du cycle RF

## Enrichissements techniques (ajoutés depuis analyse Qwen)

### Modèles de propagation à implémenter

| Contexte | Modèle recommandé |
|---|---|
| Urbain dense | ITU-R P.1411 ou COST-231 Walfisch-Ikegami |
| Suburbain / Rural | ITU-R P.1546 ou Okumura-Hata |
| 5G mmWave | ITU-R P.2108 (bâtiments + pluie) |

### Librairies Python à utiliser

- **GeoPandas** — manipulation de données géospatiales
- **Shapely** — calcul d'intersections (overlap / trous)
- **Folium** — cartographie interactive côté Python

### Sources de données terrain (gratuites)

| Donnée | Source |
|---|---|
| Relief (SRTM 30m) | Copernicus DEM ou NASA SRTM |
| Occupation des sols (clutter) | OpenStreetMap (Overpass API) ou Corine Land Cover |

### Stack backend complète

FastAPI + PostgreSQL + GeoPandas + Shapely + Folium + Mapbox GL JS (frontend)

## Détail des 8 modules

(Voir README.md du repo rf-planner-app pour le détail complet)

1. Estimation couverture & Link Budget
2. Link Budget Calculator (Okumura-Hata, COST-231, etc.)
3. Placement des sites (grille hexagonale, GeoPandas + Shapely)
4. Planification voisinage (export multi-vendor)
5. PCI / PRACH / TAC Planning
6. Nominal Planning
7. Simulateur de scénarios
8. Import terrain réel (SRTM + Clutter)

## Cas d'usage cible

Opérateur (Digicel, Orange, MTN) ou intégrateur (Huawei, Ericsson, Nokia) qui **conçoit un réseau avant déploiement**.

**Temps gagné** : design réseau de 2 semaines → 1 journée.

## Valeur stratégique

**"One-Man RF Tech Company"** : couvre les 4 phases du cycle RF complet.

| Phase | Outil | Utilisateur |
|---|---|---|
| 1. Conception | **RF Planner** | RF Planner / Architecte |
| 2. Intégration | RF Engineering 2.0 | Ingénieur NOC |
| 3. Analyse | RF Analytics | Manager RF |
| 4. Terrain | RF Optimizer Tools | Technicien field |

## Date de création

10 octobre 2026