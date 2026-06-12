from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Building, Enterprise, Meter
from app.schemas.schemas import (
    BuildingCreate,
    BuildingUpdate,
    BuildingResponse,
    EnterpriseCreate,
    EnterpriseUpdate,
    EnterpriseResponse,
    MeterCreate,
    MeterUpdate,
    MeterResponse,
    GenericResponse,
)
from app.utils.auth import get_current_user, require_roles

router = APIRouter(prefix="", tags=["园区管理"])


# ==================== 楼栋 CRUD ====================

@router.post("/buildings", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
def create_building(
    building_in: BuildingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager")),
):
    if building_in.code:
        existing = db.query(Building).filter(Building.code == building_in.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"楼栋编码 {building_in.code} 已存在",
            )
    building = Building(**building_in.model_dump())
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


@router.get("/buildings", response_model=List[BuildingResponse])
def list_buildings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    park_zone: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Building)
    if status_filter:
        query = query.filter(Building.status == status_filter)
    if park_zone:
        query = query.filter(Building.park_zone == park_zone)
    if keyword:
        query = query.filter(
            (Building.name.contains(keyword)) | (Building.code.contains(keyword))
        )
    buildings = query.offset(skip).limit(limit).all()
    return buildings


@router.get("/buildings/{building_id}", response_model=BuildingResponse)
def get_building(
    building_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"楼栋 ID {building_id} 不存在",
        )
    return building


@router.put("/buildings/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: int,
    building_in: BuildingUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager")),
):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"楼栋 ID {building_id} 不存在",
        )
    update_data = building_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(building, field, value)
    db.commit()
    db.refresh(building)
    return building


@router.delete("/buildings/{building_id}", response_model=GenericResponse)
def delete_building(
    building_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager")),
):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"楼栋 ID {building_id} 不存在",
        )
    if building.enterprises or building.meters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该楼栋下存在关联的企业或表计，无法删除",
        )
    db.delete(building)
    db.commit()
    return GenericResponse(message=f"楼栋 {building.name} 已删除")


# ==================== 企业 CRUD ====================

@router.post("/enterprises", response_model=EnterpriseResponse, status_code=status.HTTP_201_CREATED)
def create_enterprise(
    enterprise_in: EnterpriseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager")),
):
    if enterprise_in.code:
        existing = db.query(Enterprise).filter(Enterprise.code == enterprise_in.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"企业编码 {enterprise_in.code} 已存在",
            )
    if enterprise_in.building_id:
        building = db.query(Building).filter(Building.id == enterprise_in.building_id).first()
        if not building:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"关联的楼栋 ID {enterprise_in.building_id} 不存在",
            )
    enterprise = Enterprise(**enterprise_in.model_dump())
    db.add(enterprise)
    db.commit()
    db.refresh(enterprise)
    return enterprise


@router.get("/enterprises", response_model=List[EnterpriseResponse])
def list_enterprises(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    building_id: Optional[int] = None,
    industry: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Enterprise)
    if status_filter:
        query = query.filter(Enterprise.status == status_filter)
    if building_id:
        query = query.filter(Enterprise.building_id == building_id)
    if industry:
        query = query.filter(Enterprise.industry == industry)
    if keyword:
        query = query.filter(
            (Enterprise.name.contains(keyword)) | (Enterprise.code.contains(keyword))
        )
    enterprises = query.offset(skip).limit(limit).all()
    return enterprises


@router.get("/enterprises/{enterprise_id}", response_model=EnterpriseResponse)
def get_enterprise(
    enterprise_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    if not enterprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"企业 ID {enterprise_id} 不存在",
        )
    return enterprise


@router.put("/enterprises/{enterprise_id}", response_model=EnterpriseResponse)
def update_enterprise(
    enterprise_id: int,
    enterprise_in: EnterpriseUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager")),
):
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    if not enterprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"企业 ID {enterprise_id} 不存在",
        )
    update_data = enterprise_in.model_dump(exclude_unset=True)
    if "building_id" in update_data and update_data["building_id"] is not None:
        building = db.query(Building).filter(Building.id == update_data["building_id"]).first()
        if not building:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"关联的楼栋 ID {update_data['building_id']} 不存在",
            )
    for field, value in update_data.items():
        setattr(enterprise, field, value)
    db.commit()
    db.refresh(enterprise)
    return enterprise


@router.delete("/enterprises/{enterprise_id}", response_model=GenericResponse)
def delete_enterprise(
    enterprise_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager")),
):
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    if not enterprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"企业 ID {enterprise_id} 不存在",
        )
    if enterprise.users or enterprise.meters or enterprise.energy_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该企业下存在关联的用户、表计或能耗数据，无法删除",
        )
    db.delete(enterprise)
    db.commit()
    return GenericResponse(message=f"企业 {enterprise.name} 已删除")


# ==================== 表计 CRUD ====================

@router.post("/meters", response_model=MeterResponse, status_code=status.HTTP_201_CREATED)
def create_meter(
    meter_in: MeterCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager", "property_manager")),
):
    existing = db.query(Meter).filter(Meter.code == meter_in.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"表计编码 {meter_in.code} 已存在",
        )
    if meter_in.building_id:
        building = db.query(Building).filter(Building.id == meter_in.building_id).first()
        if not building:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"关联的楼栋 ID {meter_in.building_id} 不存在",
            )
    if meter_in.enterprise_id:
        enterprise = db.query(Enterprise).filter(Enterprise.id == meter_in.enterprise_id).first()
        if not enterprise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"关联的企业 ID {meter_in.enterprise_id} 不存在",
            )
    meter = Meter(**meter_in.model_dump())
    db.add(meter)
    db.commit()
    db.refresh(meter)
    return meter


@router.get("/meters", response_model=List[MeterResponse])
def list_meters(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    building_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    meter_type: Optional[str] = None,
    energy_type: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Meter)
    if status_filter:
        query = query.filter(Meter.status == status_filter)
    if building_id:
        query = query.filter(Meter.building_id == building_id)
    if enterprise_id:
        query = query.filter(Meter.enterprise_id == enterprise_id)
    if meter_type:
        query = query.filter(Meter.meter_type == meter_type)
    if energy_type:
        query = query.filter(Meter.energy_type == energy_type)
    if keyword:
        query = query.filter(
            (Meter.name.contains(keyword)) | (Meter.code.contains(keyword))
        )
    meters = query.offset(skip).limit(limit).all()
    return meters


@router.get("/meters/{meter_id}", response_model=MeterResponse)
def get_meter(
    meter_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"表计 ID {meter_id} 不存在",
        )
    return meter


@router.put("/meters/{meter_id}", response_model=MeterResponse)
def update_meter(
    meter_id: int,
    meter_in: MeterUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager", "property_manager")),
):
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"表计 ID {meter_id} 不存在",
        )
    update_data = meter_in.model_dump(exclude_unset=True)
    if "building_id" in update_data and update_data["building_id"] is not None:
        building = db.query(Building).filter(Building.id == update_data["building_id"]).first()
        if not building:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"关联的楼栋 ID {update_data['building_id']} 不存在",
            )
    if "enterprise_id" in update_data and update_data["enterprise_id"] is not None:
        enterprise = db.query(Enterprise).filter(Enterprise.id == update_data["enterprise_id"]).first()
        if not enterprise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"关联的企业 ID {update_data['enterprise_id']} 不存在",
            )
    for field, value in update_data.items():
        setattr(meter, field, value)
    db.commit()
    db.refresh(meter)
    return meter


@router.delete("/meters/{meter_id}", response_model=GenericResponse)
def delete_meter(
    meter_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager", "property_manager")),
):
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"表计 ID {meter_id} 不存在",
        )
    if meter.energy_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该表计下存在关联的能耗数据，无法删除",
        )
    db.delete(meter)
    db.commit()
    return GenericResponse(message=f"表计 {meter.name} 已删除")


# ==================== 表计绑定 ====================

@router.post("/meters/{meter_id}/bind-enterprise", response_model=MeterResponse)
def bind_meter_to_enterprise(
    meter_id: int,
    enterprise_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager", "property_manager")),
):
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"表计 ID {meter_id} 不存在",
        )
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    if not enterprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"企业 ID {enterprise_id} 不存在",
        )
    meter.enterprise_id = enterprise_id
    db.commit()
    db.refresh(meter)
    return meter


@router.post("/meters/{meter_id}/bind-building", response_model=MeterResponse)
def bind_meter_to_building(
    meter_id: int,
    building_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "park_manager", "property_manager")),
):
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"表计 ID {meter_id} 不存在",
        )
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"楼栋 ID {building_id} 不存在",
        )
    meter.building_id = building_id
    db.commit()
    db.refresh(meter)
    return meter
