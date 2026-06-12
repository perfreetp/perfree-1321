from datetime import datetime, timedelta, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import get_db
from app.config import settings
from app.models.models import CarbonData, CarbonBudget, LoadForecast, EnergyData, Enterprise
from app.schemas.schemas import (
    CarbonCalculateQuery,
    CarbonCalculateResult,
    CarbonBudgetCreate,
    CarbonBudgetUpdate,
    CarbonBudgetResponse,
    CarbonDataResponse,
    LoadForecastQuery,
    LoadForecastItem,
    LoadForecastResponse,
    GenericResponse,
    CarbonBudgetAllocate,
)
from app.utils.auth import get_current_user, require_roles

router = APIRouter(prefix="", tags=["碳排放与负荷预测"])


def get_carbon_factor(energy_type: str) -> float:
    if energy_type == "electricity":
        return settings.CARBON_FACTOR_ELECTRICITY
    elif energy_type == "gas":
        return settings.CARBON_FACTOR_GAS
    elif energy_type == "heat":
        return settings.CARBON_FACTOR_HEAT
    elif energy_type == "water":
        return settings.CARBON_FACTOR_WATER
    return 0.0


@router.post("/carbon/calculate", response_model=GenericResponse)
def calculate_carbon(
    query_in: CarbonCalculateQuery,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        enterprise_id = current_user.enterprise_id
    else:
        enterprise_id = query_in.enterprise_id

    query = db.query(EnergyData)

    if enterprise_id:
        query = query.filter(EnergyData.enterprise_id == enterprise_id)
    if query_in.energy_type:
        query = query.filter(EnergyData.energy_type == query_in.energy_type)
    if query_in.start_date:
        start_dt = datetime.combine(query_in.start_date, datetime.min.time())
        query = query.filter(EnergyData.data_time >= start_dt)
    if query_in.end_date:
        end_dt = datetime.combine(query_in.end_date, datetime.max.time())
        query = query.filter(EnergyData.data_time <= end_dt)

    raw_data = query.all()

    usage_map = {}
    for item in raw_data:
        etype = item.energy_type
        if etype not in usage_map:
            usage_map[etype] = 0.0
        usage_map[etype] += item.usage_value

    results = []
    total_carbon = 0.0
    for etype, usage in usage_map.items():
        factor = get_carbon_factor(etype)
        carbon = usage * factor
        total_carbon += carbon
        results.append(
            CarbonCalculateResult(
                energy_type=etype,
                energy_usage=round(usage, 4),
                carbon_factor=factor,
                carbon_emission=round(carbon, 4),
            )
        )

    data_date = query_in.end_date or date.today()
    for r in results:
        existing = (
            db.query(CarbonData)
            .filter(
                CarbonData.enterprise_id == enterprise_id,
                CarbonData.energy_type == r.energy_type,
                CarbonData.data_date == data_date,
            )
            .first()
        )
        if existing:
            existing.carbon_emission = r.carbon_emission
        else:
            carbon_record = CarbonData(
                enterprise_id=enterprise_id,
                energy_type=r.energy_type,
                carbon_emission=r.carbon_emission,
                data_date=data_date,
                period="day",
            )
            db.add(carbon_record)
    db.commit()

    return GenericResponse(
        code=200,
        message="碳排换算成功",
        data={
            "enterprise_id": enterprise_id,
            "start_date": query_in.start_date,
            "end_date": query_in.end_date,
            "total_carbon_emission": round(total_carbon, 4),
            "items": [r.model_dump() for r in results],
        },
    )


@router.get("/carbon/data", response_model=GenericResponse)
def get_carbon_data(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    energy_type: Optional[str] = Query(None, description="能源类型"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(CarbonData)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(CarbonData.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(CarbonData.enterprise_id == enterprise_id)
    if energy_type:
        query = query.filter(CarbonData.energy_type == energy_type)
    if start_date:
        query = query.filter(CarbonData.data_date >= start_date)
    if end_date:
        query = query.filter(CarbonData.data_date <= end_date)

    total = query.count()
    items = query.order_by(CarbonData.data_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "energy_type": item.energy_type,
            "carbon_emission": item.carbon_emission,
            "data_date": item.data_date,
            "period": item.period,
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


@router.post("/carbon/budget", response_model=GenericResponse)
def create_carbon_budget(
    budget_in: CarbonBudgetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    enterprise = db.query(Enterprise).filter(Enterprise.id == budget_in.enterprise_id).first()
    if not enterprise:
        raise HTTPException(status_code=404, detail="企业不存在")

    if budget_in.start_date >= budget_in.end_date:
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    existing = (
        db.query(CarbonBudget)
        .filter(
            CarbonBudget.enterprise_id == budget_in.enterprise_id,
            and_(
                CarbonBudget.start_date <= budget_in.end_date,
                CarbonBudget.end_date >= budget_in.start_date,
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该企业在指定时间段内已有碳预算")

    db_budget = CarbonBudget(**budget_in.model_dump())
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)

    return GenericResponse(
        code=201,
        message="碳预算创建成功",
        data={"id": db_budget.id},
    )


@router.get("/carbon/budget", response_model=GenericResponse)
def list_carbon_budgets(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    period: Optional[str] = Query(None, description="预算周期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(CarbonBudget)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(CarbonBudget.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(CarbonBudget.enterprise_id == enterprise_id)
    if period:
        query = query.filter(CarbonBudget.period == period)

    total = query.count()
    items = query.order_by(CarbonBudget.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "budget_value": item.budget_value,
            "period": item.period,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "allocated_by": item.allocated_by,
            "description": item.description,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
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


@router.put("/carbon/budget/{budget_id}", response_model=GenericResponse)
def update_carbon_budget(
    budget_id: int,
    budget_in: CarbonBudgetUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    budget = db.query(CarbonBudget).filter(CarbonBudget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="碳预算不存在")

    update_data = budget_in.model_dump(exclude_unset=True)

    if "start_date" in update_data and "end_date" in update_data:
        if update_data["start_date"] >= update_data["end_date"]:
            raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")
    elif "start_date" in update_data:
        if update_data["start_date"] >= budget.end_date:
            raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")
    elif "end_date" in update_data:
        if budget.start_date >= update_data["end_date"]:
            raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    for key, value in update_data.items():
        setattr(budget, key, value)

    db.commit()
    db.refresh(budget)

    return GenericResponse(
        code=200,
        message="碳预算更新成功",
        data={"id": budget.id},
    )


@router.delete("/carbon/budget/{budget_id}", response_model=GenericResponse)
def delete_carbon_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    budget = db.query(CarbonBudget).filter(CarbonBudget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="碳预算不存在")
    db.delete(budget)
    db.commit()

    return GenericResponse(
        code=200,
        message="碳预算删除成功",
        data={"id": budget_id},
    )


@router.post("/carbon/budget/allocate", response_model=GenericResponse)
def allocate_carbon_budget(
    allocate_in: CarbonBudgetAllocate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    total_budget = allocate_in.total_budget
    start_date = allocate_in.start_date
    end_date = allocate_in.end_date
    period = allocate_in.period
    allocate_type = allocate_in.allocate_type
    building_id = allocate_in.building_id

    if allocate_type not in ["area", "employee", "history"]:
        raise HTTPException(status_code=400, detail="分摊方式必须是 area(按面积)/employee(按人数)/history(按历史用量)")

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="开始日期和结束日期不能为空")

    if start_date >= end_date:
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    if building_id is not None:
        building = db.query(Enterprise.building_id).filter(Enterprise.building_id == building_id).first()
        if not building:
            raise HTTPException(status_code=400, detail=f"楼栋ID {building_id} 不存在或无关联企业")

    enterprises_query = db.query(Enterprise).filter(Enterprise.status == "active")
    if building_id:
        enterprises_query = enterprises_query.filter(Enterprise.building_id == building_id)
    enterprises = enterprises_query.all()

    if not enterprises:
        raise HTTPException(status_code=404, detail="未找到可分配的企业")

    weights = {}
    total_weight = 0.0

    for ent in enterprises:
        if allocate_type == "area":
            weight = ent.occupied_area or 0.0
        elif allocate_type == "employee":
            weight = ent.employee_count or 0.0
        elif allocate_type == "history":
            start_dt = datetime.combine(start_date, datetime.min.time()) - timedelta(days=365)
            end_dt = datetime.combine(end_date, datetime.max.time()) - timedelta(days=365)
            hist_carbon = (
                db.query(func.sum(CarbonData.carbon_emission))
                .filter(
                    CarbonData.enterprise_id == ent.id,
                    CarbonData.data_date >= start_dt.date(),
                    CarbonData.data_date <= end_dt.date(),
                )
                .scalar()
                or 0.0
            )
            weight = hist_carbon
        else:
            weight = 1.0
        weights[ent.id] = weight
        total_weight += weight

    if total_weight <= 0:
        raise HTTPException(status_code=400, detail="总权重为0，无法分配")

    allocated = []
    for ent in enterprises:
        share = total_budget * (weights[ent.id] / total_weight)
        existing = (
            db.query(CarbonBudget)
            .filter(
                CarbonBudget.enterprise_id == ent.id,
                and_(
                    CarbonBudget.start_date <= end_date,
                    CarbonBudget.end_date >= start_date,
                ),
            )
            .first()
        )
        if existing:
            existing.budget_value = round(share, 4)
            existing.allocated_by = allocate_type
            existing.start_date = start_date
            existing.end_date = end_date
            existing.period = period
            budget_id = existing.id
        else:
            new_budget = CarbonBudget(
                enterprise_id=ent.id,
                budget_value=round(share, 4),
                period=period,
                start_date=start_date,
                end_date=end_date,
                allocated_by=allocate_type,
                description=f"按{allocate_type}自动分配{'（楼栋ID:' + str(building_id) + '）' if building_id else ''}",
            )
            db.add(new_budget)
            db.flush()
            budget_id = new_budget.id

        allocated.append(
            {
                "budget_id": budget_id,
                "enterprise_id": ent.id,
                "enterprise_name": ent.name,
                "budget_value": round(share, 4),
                "weight": weights[ent.id],
                "weight_ratio": round(weights[ent.id] / total_weight * 100, 2),
            }
        )

    db.commit()

    return GenericResponse(
        code=200,
        message="碳预算分摊成功",
        data={
            "total_budget": total_budget,
            "allocate_type": allocate_type,
            "start_date": start_date,
            "end_date": end_date,
            "building_id": building_id,
            "period": period,
            "allocated_count": len(allocated),
            "items": allocated,
        },
    )


@router.post("/forecast/generate", response_model=GenericResponse)
def generate_load_forecast(
    query_in: LoadForecastQuery,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        enterprise_id = current_user.enterprise_id
    else:
        enterprise_id = query_in.enterprise_id

    energy_type = query_in.energy_type or "electricity"
    forecast_hours = query_in.forecast_hours or 24
    model_type = query_in.model_type or "moving_average"

    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)

    query = db.query(EnergyData).filter(
        EnergyData.enterprise_id == enterprise_id,
        EnergyData.energy_type == energy_type,
        EnergyData.data_time >= start_time,
        EnergyData.data_time <= end_time,
    )
    raw_data = query.order_by(EnergyData.data_time.asc()).all()

    if not raw_data:
        raise HTTPException(status_code=400, detail="历史数据不足，无法进行预测")

    hourly_load = {}
    for item in raw_data:
        dt = item.data_time.replace(minute=0, second=0, microsecond=0)
        if dt not in hourly_load:
            hourly_load[dt] = 0.0
        hourly_load[dt] += item.usage_value

    sorted_hours = sorted(hourly_load.keys())

    forecast_items = []
    now = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    if model_type == "linear_regression" and len(sorted_hours) >= 2:
        x_vals = list(range(len(sorted_hours)))
        y_vals = [hourly_load[h] for h in sorted_hours]
        n = len(x_vals)
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n
        numerator = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
        denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))
        if denominator > 0:
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean
            for i in range(forecast_hours):
                forecast_time = now + timedelta(hours=i)
                x_next = n + i
                forecast_value = max(0.0, slope * x_next + intercept)
                forecast_items.append(
                    LoadForecastItem(
                        forecast_time=forecast_time,
                        forecast_value=round(forecast_value, 4),
                        energy_type=energy_type,
                    )
                )
        else:
            model_type = "moving_average"

    if model_type != "linear_regression" or not forecast_items:
        window_size = min(24, len(sorted_hours))
        recent_values = [hourly_load[h] for h in sorted_hours[-window_size:]]
        avg_value = sum(recent_values) / len(recent_values) if recent_values else 0.0

        same_hour_avg = {}
        for h in sorted_hours:
            hour_key = h.hour
            if hour_key not in same_hour_avg:
                same_hour_avg[hour_key] = []
            same_hour_avg[hour_key].append(hourly_load[h])

        for i in range(forecast_hours):
            forecast_time = now + timedelta(hours=i)
            hour_key = forecast_time.hour
            if hour_key in same_hour_avg and same_hour_avg[hour_key]:
                forecast_value = sum(same_hour_avg[hour_key]) / len(same_hour_avg[hour_key])
            else:
                forecast_value = avg_value
            forecast_value = max(0.0, forecast_value)
            forecast_items.append(
                LoadForecastItem(
                    forecast_time=forecast_time,
                    forecast_value=round(forecast_value, 4),
                    energy_type=energy_type,
                )
            )

    db.query(LoadForecast).filter(
        LoadForecast.enterprise_id == enterprise_id,
        LoadForecast.energy_type == energy_type,
        LoadForecast.forecast_time >= now,
    ).delete(synchronize_session=False)

    for item in forecast_items:
        forecast_record = LoadForecast(
            enterprise_id=enterprise_id,
            energy_type=item.energy_type,
            forecast_time=item.forecast_time,
            forecast_value=item.forecast_value,
            forecast_period="hour",
            model_type=model_type,
        )
        db.add(forecast_record)
    db.commit()

    return GenericResponse(
        code=200,
        message="负荷预测生成成功",
        data={
            "enterprise_id": enterprise_id,
            "energy_type": energy_type,
            "forecast_hours": forecast_hours,
            "model_type": model_type,
            "items": [item.model_dump() for item in forecast_items],
        },
    )


@router.get("/forecast/data", response_model=GenericResponse)
def get_forecast_data(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    energy_type: Optional[str] = Query(None, description="能源类型"),
    model_type: Optional[str] = Query(None, description="预测模型"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(LoadForecast)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(LoadForecast.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(LoadForecast.enterprise_id == enterprise_id)
    if energy_type:
        query = query.filter(LoadForecast.energy_type == energy_type)
    if model_type:
        query = query.filter(LoadForecast.model_type == model_type)
    if start_time:
        query = query.filter(LoadForecast.forecast_time >= start_time)
    if end_time:
        query = query.filter(LoadForecast.forecast_time <= end_time)

    total = query.count()
    items = query.order_by(LoadForecast.forecast_time.asc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "energy_type": item.energy_type,
            "forecast_time": item.forecast_time,
            "forecast_value": item.forecast_value,
            "actual_value": item.actual_value,
            "forecast_period": item.forecast_period,
            "model_type": item.model_type,
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
