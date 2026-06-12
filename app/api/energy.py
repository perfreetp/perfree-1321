from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db
from app.config import settings
from app.models.models import EnergyData, Enterprise, Building, Meter
from app.schemas.schemas import (
    EnergyDataCreate,
    EnergyDataResponse,
    EnergySummaryQuery,
    EnergySummaryItem,
    RealtimeLoadQuery,
    RealtimeLoadItem,
    PeakValleyPriceQuery,
    PeakValleyPriceResult,
    GenericResponse,
)
from app.utils.auth import get_current_user, require_roles

router = APIRouter(prefix="/energy", tags=["能耗管理"])


PEAK_HOURS = list(range(8, 11)) + list(range(18, 23))
FLAT_HOURS = list(range(11, 18))
VALLEY_HOURS = list(range(0, 8)) + [23]


def get_peak_type(hour: int) -> str:
    if hour in PEAK_HOURS:
        return "peak"
    elif hour in FLAT_HOURS:
        return "flat"
    else:
        return "valley"


def get_energy_price(energy_type: str, peak_type: Optional[str] = None) -> float:
    if energy_type == "electricity":
        if peak_type == "peak":
            return settings.ELECTRICITY_PEAK_PRICE
        elif peak_type == "valley":
            return settings.ELECTRICITY_VALLEY_PRICE
        else:
            return settings.ELECTRICITY_FLAT_PRICE
    elif energy_type == "gas":
        return settings.GAS_PRICE
    elif energy_type == "heat":
        return settings.HEAT_PRICE
    elif energy_type == "water":
        return settings.WATER_PRICE
    return 0.0


@router.post("/data", response_model=GenericResponse)
def create_energy_data(
    data_in: EnergyDataCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    meter = db.query(Meter).filter(Meter.id == data_in.meter_id).first()
    if not meter:
        raise HTTPException(status_code=404, detail="电表不存在")

    enterprise_id = data_in.enterprise_id or meter.enterprise_id
    peak_type = data_in.peak_type or get_peak_type(data_in.data_time.hour)
    price = data_in.price if data_in.price != 0 else get_energy_price(data_in.energy_type, peak_type)

    energy_data = EnergyData(
        meter_id=data_in.meter_id,
        enterprise_id=enterprise_id,
        energy_type=data_in.energy_type,
        usage_value=data_in.usage_value,
        data_time=data_in.data_time,
        data_period=data_in.data_period,
        price=price,
        peak_type=peak_type,
    )
    db.add(energy_data)
    db.commit()
    db.refresh(energy_data)

    return GenericResponse(
        code=201,
        message="能耗数据录入成功",
        data={"id": energy_data.id},
    )


@router.get("/data", response_model=GenericResponse)
def get_energy_data_list(
    meter_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    building_id: Optional[int] = None,
    energy_type: Optional[str] = None,
    park_zone: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(EnergyData).join(Meter, EnergyData.meter_id == Meter.id)

    if building_id or park_zone:
        query = query.join(Building, Meter.building_id == Building.id)

    if meter_id:
        query = query.filter(EnergyData.meter_id == meter_id)
    if enterprise_id:
        query = query.filter(EnergyData.enterprise_id == enterprise_id)
    if building_id:
        query = query.filter(Meter.building_id == building_id)
    if park_zone:
        query = query.filter(Building.park_zone == park_zone)
    if energy_type:
        query = query.filter(EnergyData.energy_type == energy_type)
    if start_time:
        query = query.filter(EnergyData.data_time >= start_time)
    if end_time:
        query = query.filter(EnergyData.data_time <= end_time)

    total = query.count()
    items = query.order_by(EnergyData.data_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "meter_id": item.meter_id,
            "enterprise_id": item.enterprise_id,
            "energy_type": item.energy_type,
            "usage_value": item.usage_value,
            "data_time": item.data_time,
            "data_period": item.data_period,
            "price": item.price,
            "peak_type": item.peak_type,
            "created_at": item.created_at,
        }
        for item in items
    ]

    return GenericResponse(
        code=200,
        message="success",
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": data,
        },
    )


@router.post("/summary", response_model=GenericResponse)
def get_energy_summary(
    query_in: EnergySummaryQuery,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    group_by = query_in.group_by or "day"
    if group_by not in ["hour", "day", "month", "year"]:
        raise HTTPException(status_code=400, detail="group_by 参数必须是 hour/day/month/year")

    query = db.query(EnergyData).join(Meter, EnergyData.meter_id == Meter.id)

    if query_in.building_id or query_in.park_zone:
        query = query.join(Building, Meter.building_id == Building.id)

    if query_in.enterprise_id:
        query = query.filter(EnergyData.enterprise_id == query_in.enterprise_id)
    if query_in.building_id:
        query = query.filter(Meter.building_id == query_in.building_id)
    if query_in.park_zone:
        query = query.filter(Building.park_zone == query_in.park_zone)
    if query_in.energy_type:
        query = query.filter(EnergyData.energy_type == query_in.energy_type)
    if query_in.start_time:
        query = query.filter(EnergyData.data_time >= query_in.start_time)
    if query_in.end_time:
        query = query.filter(EnergyData.data_time <= query_in.end_time)

    raw_data = query.order_by(EnergyData.data_time.asc()).all()

    result_map = {}

    for item in raw_data:
        dt = item.data_time
        if group_by == "hour":
            time_label = dt.strftime("%Y-%m-%d %H:00")
        elif group_by == "day":
            time_label = dt.strftime("%Y-%m-%d")
        elif group_by == "month":
            time_label = dt.strftime("%Y-%m")
        else:
            time_label = dt.strftime("%Y")

        energy_type = item.energy_type
        key = (time_label, energy_type)

        if key not in result_map:
            result_map[key] = {
                "time_label": time_label,
                "energy_type": energy_type,
                "usage_value": 0.0,
                "cost": 0.0,
                "peak_usage": 0.0,
                "flat_usage": 0.0,
                "valley_usage": 0.0,
            }

        result_map[key]["usage_value"] += item.usage_value
        result_map[key]["cost"] += item.usage_value * item.price

        if item.peak_type == "peak":
            result_map[key]["peak_usage"] += item.usage_value
        elif item.peak_type == "flat":
            result_map[key]["flat_usage"] += item.usage_value
        elif item.peak_type == "valley":
            result_map[key]["valley_usage"] += item.usage_value

    summary_list = sorted(
        result_map.values(),
        key=lambda x: (x["time_label"], x["energy_type"]),
    )

    return GenericResponse(
        code=200,
        message="success",
        data={
            "group_by": group_by,
            "total_count": len(summary_list),
            "items": summary_list,
        },
    )


@router.post("/realtime", response_model=GenericResponse)
def get_realtime_load(
    query_in: RealtimeLoadQuery,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    query = db.query(EnergyData).join(Meter, EnergyData.meter_id == Meter.id)

    if query_in.building_id:
        query = query.filter(Meter.building_id == query_in.building_id)
    if query_in.enterprise_id:
        query = query.filter(EnergyData.enterprise_id == query_in.enterprise_id)

    energy_type = query_in.energy_type or "electricity"
    query = query.filter(
        EnergyData.energy_type == energy_type,
        EnergyData.data_time >= start_time,
        EnergyData.data_time <= end_time,
    )

    raw_data = query.order_by(EnergyData.data_time.asc()).all()

    load_map = {}
    for item in raw_data:
        dt = item.data_time.replace(minute=0, second=0, microsecond=0)
        if dt not in load_map:
            load_map[dt] = 0.0
        load_map[dt] += item.usage_value

    current = start_time.replace(minute=0, second=0, microsecond=0)
    load_list = []
    while current <= end_time:
        load_list.append(
            RealtimeLoadItem(
                time_point=current,
                load_value=load_map.get(current, 0.0),
                energy_type=energy_type,
            )
        )
        current += timedelta(hours=1)

    return GenericResponse(
        code=200,
        message="success",
        data={
            "energy_type": energy_type,
            "start_time": start_time,
            "end_time": end_time,
            "items": [item.model_dump() for item in load_list],
        },
    )


@router.post("/peak-valley-price", response_model=GenericResponse)
def calculate_peak_valley_price(
    query_in: PeakValleyPriceQuery,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    energy_type = query_in.energy_type or "electricity"

    start_dt = datetime.combine(query_in.start_date, datetime.min.time())
    end_dt = datetime.combine(query_in.end_date, datetime.max.time())

    query = db.query(EnergyData).filter(
        EnergyData.enterprise_id == query_in.enterprise_id,
        EnergyData.energy_type == energy_type,
        EnergyData.data_time >= start_dt,
        EnergyData.data_time <= end_dt,
    )

    raw_data = query.all()

    peak_usage = 0.0
    flat_usage = 0.0
    valley_usage = 0.0

    for item in raw_data:
        peak_type = item.peak_type or get_peak_type(item.data_time.hour)
        if peak_type == "peak":
            peak_usage += item.usage_value
        elif peak_type == "valley":
            valley_usage += item.usage_value
        else:
            flat_usage += item.usage_value

    if energy_type == "electricity":
        peak_price = settings.ELECTRICITY_PEAK_PRICE
        flat_price = settings.ELECTRICITY_FLAT_PRICE
        valley_price = settings.ELECTRICITY_VALLEY_PRICE
    else:
        single_price = get_energy_price(energy_type)
        peak_price = flat_price = valley_price = single_price

    peak_amount = peak_usage * peak_price
    flat_amount = flat_usage * flat_price
    valley_amount = valley_usage * valley_price
    total_usage = peak_usage + flat_usage + valley_usage
    total_amount = peak_amount + flat_amount + valley_amount

    result = PeakValleyPriceResult(
        peak_usage=peak_usage,
        peak_price=peak_price,
        peak_amount=peak_amount,
        flat_usage=flat_usage,
        flat_price=flat_price,
        flat_amount=flat_amount,
        valley_usage=valley_usage,
        valley_price=valley_price,
        valley_amount=valley_amount,
        total_usage=total_usage,
        total_amount=total_amount,
    )

    return GenericResponse(
        code=200,
        message="success",
        data=result.model_dump(),
    )
