from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base
import uuid
from pydantic import BaseModel
from typing import Optional

# ==========================================
# Modèles SQLAlchemy (Base de données)
# ==========================================
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(150), nullable=False)
    frequency_band = Column(String(20))
    technology = Column(String(20), default="5G_NR")
    target_coverage_pct = Column(Float, default=95.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Site(Base):
    __tablename__ = "sites"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(String(50), nullable=False)
    vendor = Column(String(50))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float)
    antenna_height_m = Column(Float, default=30.0)
    azimuth_deg = Column(Integer, default=0)
    mechanical_tilt_deg = Column(Float, default=2.0)
    tx_power_dbm = Column(Float, default=43.0)
    status = Column(String(20), default="NOMINAL")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class NeighborRelation(Base):
    __tablename__ = "neighbor_relations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    source_site_id = Column(UUID(as_uuid=True), nullable=False)
    target_site_id = Column(UUID(as_uuid=True), nullable=False)
    distance_m = Column(Float)
    is_bidirectional = Column(Boolean, default=True)
    vendor_script_mml = Column(Text)

# ==========================================
# Modèles Pydantic (API Request/Response)
# ==========================================
class LinkBudgetRequest(BaseModel):
    center_lat: float
    center_lon: float
    frequency_mhz: float
    antenna_height_m: float
    clutter_loss_db: float
    propagation_model: str
    target_area_km2: float

class LinkBudgetResponse(BaseModel):
    mapl_db: float
    radius_km: float
    estimated_sites: int
    hexagons_geojson: dict

class NeighborRequest(BaseModel):
    project_id: str
    source_site_id: str
    detection_radius_m: float = 2000.0
    vendor: str = "Huawei"

class NeighborResponse(BaseModel):
    neighbors: list
    vendor_script: str