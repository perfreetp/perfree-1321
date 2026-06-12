from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db
from app.config import settings
from app.models.models import (
    Bill,
    MonthlyReport,
    Alarm,
    AlertSubscription,
    Enterprise,
    Building,
    EnergyData,
    CarbonData,
    Quota,
    User,
)
from app.schemas.schemas import (
    BillCreate,
    BillUpdate,
    BillResponse,
    BillSplitQuery,
    BillSplitItem,
    MonthlyReportCreate,
    MonthlyReportResponse,
    MonthlyReportGenerate,
    EnterpriseRankingQuery,
    EnterpriseRankingItem,
    AlarmCreate,
    AlarmUpdate,
    AlarmResponse,
    AlertSubscriptionCreate,
    AlertSubscriptionUpdate,
    AlertSubscriptionResponse,
    GenericResponse,
)
from app.utils.auth import get_current_user, require_roles

router = APIRouter(tags=["账单报告与告警"])


def get_carbon_factor(energy_type: str) -> float:
    factors = {
        "electricity": settings.CARBON_FACTOR_ELECTRICITY,
        "gas": settings.CARBON_FACTOR_GAS,
        "heat": settings.CARBON_FACTOR_HEAT,
        "water": settings.CARBON_FACTOR_WATER,
    }
    return factors.get(energy_type, 0.0)


@router.post("/bills", response_model=GenericResponse)
def create_bill(
    bill_in: BillCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    enterprise = db.query(Enterprise).filter(Enterprise.id == bill_in.enterprise_id).first()
    if not enterprise:
        raise HTTPException(status_code=404, detail="企业不存在")

    bill = Bill(**bill_in.model_dump())
    db.add(bill)
    db.commit()
    db.refresh(bill)

    return GenericResponse(
        code=201,
        message="账单创建成功",
        data={"id": bill.id},
    )


@router.get("/bills", response_model=GenericResponse)
def list_bills(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    bill_month: Optional[str] = Query(None, description="账期月份，格式YYYY-MM"),
    energy_type: Optional[str] = Query(None, description="能源类型"),
    status: Optional[str] = Query(None, description="账单状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Bill).join(Enterprise, Bill.enterprise_id == Enterprise.id)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(Bill.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(Bill.enterprise_id == enterprise_id)

    if bill_month:
        query = query.filter(Bill.bill_month == bill_month)
    if energy_type:
        query = query.filter(Bill.energy_type == energy_type)
    if status:
        query = query.filter(Bill.status == status)

    total = query.count()
    items = query.order_by(Bill.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "enterprise_name": item.enterprise.name if item.enterprise else None,
            "bill_month": item.bill_month,
            "energy_type": item.energy_type,
            "usage": item.usage,
            "peak_usage": item.peak_usage,
            "flat_usage": item.flat_usage,
            "valley_usage": item.valley_usage,
            "amount": item.amount,
            "peak_amount": item.peak_amount,
            "flat_amount": item.flat_amount,
            "valley_amount": item.valley_amount,
            "status": item.status,
            "due_date": item.due_date,
            "paid_date": item.paid_date,
            "description": item.description,
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


@router.get("/bills/{bill_id}", response_model=GenericResponse)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    if current_user.role == "enterprise_user" and current_user.enterprise_id != bill.enterprise_id:
        raise HTTPException(status_code=403, detail="无权查看该账单")

    data = {
        "id": bill.id,
        "enterprise_id": bill.enterprise_id,
        "enterprise_name": bill.enterprise.name if bill.enterprise else None,
        "bill_month": bill.bill_month,
        "energy_type": bill.energy_type,
        "usage": bill.usage,
        "peak_usage": bill.peak_usage,
        "flat_usage": bill.flat_usage,
        "valley_usage": bill.valley_usage,
        "amount": bill.amount,
        "peak_amount": bill.peak_amount,
        "flat_amount": bill.flat_amount,
        "valley_amount": bill.valley_amount,
        "status": bill.status,
        "due_date": bill.due_date,
        "paid_date": bill.paid_date,
        "description": bill.description,
        "created_at": bill.created_at,
    }

    return GenericResponse(code=200, message="success", data=data)


@router.put("/bills/{bill_id}", response_model=GenericResponse)
def update_bill(
    bill_id: int,
    bill_in: BillUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager", "enterprise_user")),
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    if current_user.role == "enterprise_user" and current_user.enterprise_id != bill.enterprise_id:
        raise HTTPException(status_code=403, detail="无权修改该账单")

    update_data = bill_in.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] == "paid" and bill.status != "paid":
        if "paid_date" not in update_data:
            update_data["paid_date"] = date.today()

    for key, value in update_data.items():
        setattr(bill, key, value)

    db.commit()
    db.refresh(bill)

    return GenericResponse(
        code=200,
        message="账单更新成功",
        data={"id": bill.id, "status": bill.status},
    )


@router.post("/bills/split", response_model=GenericResponse)
def split_bill(
    split_in: BillSplitQuery,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    split_type = split_in.split_type or "area"
    if split_type not in ["area", "headcount", "usage"]:
        raise HTTPException(status_code=400, detail="分摊方式必须是 area/headcount/usage")

    enterprises_query = db.query(Enterprise)
    if split_in.building_id:
        building = db.query(Building).filter(Building.id == split_in.building_id).first()
        if not building:
            raise HTTPException(status_code=404, detail="楼栋不存在")
        enterprises_query = enterprises_query.filter(Enterprise.building_id == split_in.building_id)

    enterprises = enterprises_query.filter(Enterprise.status == "active").all()
    if not enterprises:
        raise HTTPException(status_code=400, detail="未找到可用企业")

    energy_types = ["electricity", "gas", "heat", "water"]
    result_items: List[dict] = []

    year, month = map(int, split_in.bill_month.split("-"))
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.min.time())

    for energy_type in energy_types:
        total_usage = (
            db.query(func.sum(EnergyData.usage_value))
            .filter(
                EnergyData.energy_type == energy_type,
                EnergyData.data_time >= start_dt,
                EnergyData.data_time < end_dt,
            )
            .scalar()
            or 0.0
        )

        if total_usage <= 0:
            continue

        total_weight = 0.0
        enterprise_weights = {}

        for ent in enterprises:
            if split_type == "area":
                weight = ent.occupied_area or 0.0
            elif split_type == "headcount":
                weight = ent.employee_count or 0.0
            else:
                weight = (
                    db.query(func.sum(EnergyData.usage_value))
                    .filter(
                        EnergyData.enterprise_id == ent.id,
                        EnergyData.energy_type == energy_type,
                        EnergyData.data_time >= start_dt,
                        EnergyData.data_time < end_dt,
                    )
                    .scalar()
                    or 0.0
                )
            enterprise_weights[ent.id] = weight
            total_weight += weight

        if total_weight <= 0:
            continue

        for ent in enterprises:
            weight = enterprise_weights.get(ent.id, 0.0)
            share_ratio = weight / total_weight if total_weight > 0 else 0.0
            ent_usage = total_usage * share_ratio

            if energy_type == "electricity":
                peak_price = settings.ELECTRICITY_PEAK_PRICE
                flat_price = settings.ELECTRICITY_FLAT_PRICE
                valley_price = settings.ELECTRICITY_VALLEY_PRICE
                avg_price = (peak_price + flat_price + valley_price) / 3
            elif energy_type == "gas":
                avg_price = settings.GAS_PRICE
            elif energy_type == "heat":
                avg_price = settings.HEAT_PRICE
            else:
                avg_price = settings.WATER_PRICE

            share_amount = ent_usage * avg_price

            existing_bill = (
                db.query(Bill)
                .filter(
                    Bill.enterprise_id == ent.id,
                    Bill.bill_month == split_in.bill_month,
                    Bill.energy_type == energy_type,
                )
                .first()
            )

            if existing_bill:
                existing_bill.usage = ent_usage
                existing_bill.amount = share_amount
                existing_bill.peak_usage = ent_usage * 0.3
                existing_bill.flat_usage = ent_usage * 0.5
                existing_bill.valley_usage = ent_usage * 0.2
                existing_bill.peak_amount = ent_usage * 0.3 * settings.ELECTRICITY_PEAK_PRICE if energy_type == "electricity" else 0
                existing_bill.flat_amount = ent_usage * 0.5 * settings.ELECTRICITY_FLAT_PRICE if energy_type == "electricity" else 0
                existing_bill.valley_amount = ent_usage * 0.2 * settings.ELECTRICITY_VALLEY_PRICE if energy_type == "electricity" else 0
                bill_id = existing_bill.id
            else:
                new_bill = Bill(
                    enterprise_id=ent.id,
                    bill_month=split_in.bill_month,
                    energy_type=energy_type,
                    usage=ent_usage,
                    peak_usage=ent_usage * 0.3,
                    flat_usage=ent_usage * 0.5,
                    valley_usage=ent_usage * 0.2,
                    amount=share_amount,
                    peak_amount=ent_usage * 0.3 * settings.ELECTRICITY_PEAK_PRICE if energy_type == "electricity" else 0,
                    flat_amount=ent_usage * 0.5 * settings.ELECTRICITY_FLAT_PRICE if energy_type == "electricity" else 0,
                    valley_amount=ent_usage * 0.2 * settings.ELECTRICITY_VALLEY_PRICE if energy_type == "electricity" else 0,
                    status="unpaid",
                    description=f"{split_in.bill_month} {energy_type} 账单分摊（{split_type}）",
                )
                db.add(new_bill)
                db.flush()
                bill_id = new_bill.id

            result_items.append(
                BillSplitItem(
                    enterprise_id=ent.id,
                    enterprise_name=ent.name,
                    total_usage=ent_usage,
                    share_ratio=round(share_ratio, 4),
                    share_amount=round(share_amount, 2),
                    energy_type=energy_type,
                ).model_dump()
            )
            result_items[-1]["bill_id"] = bill_id

    db.commit()

    return GenericResponse(
        code=200,
        message=f"账单分摊完成，共生成{len(result_items)}条账单记录",
        data={
            "bill_month": split_in.bill_month,
            "split_type": split_type,
            "count": len(result_items),
            "items": result_items,
        },
    )


@router.post("/reports/monthly/generate", response_model=GenericResponse)
def generate_monthly_report(
    report_in: MonthlyReportGenerate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    enterprises_query = db.query(Enterprise).filter(Enterprise.status == "active")
    if report_in.enterprise_id:
        enterprises_query = enterprises_query.filter(Enterprise.id == report_in.enterprise_id)

    enterprises = enterprises_query.all()
    if not enterprises:
        raise HTTPException(status_code=400, detail="未找到可用企业")

    year, month = map(int, report_in.report_month.split("-"))
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.min.time())

    generated_reports = []
    enterprise_stats = []

    for ent in enterprises:
        energy_data_list = (
            db.query(EnergyData)
            .filter(
                EnergyData.enterprise_id == ent.id,
                EnergyData.data_time >= start_dt,
                EnergyData.data_time < end_dt,
            )
            .all()
        )

        energy_electricity = 0.0
        energy_gas = 0.0
        energy_heat = 0.0
        energy_water = 0.0
        cost_total = 0.0

        for ed in energy_data_list:
            if ed.energy_type == "electricity":
                energy_electricity += ed.usage_value
            elif ed.energy_type == "gas":
                energy_gas += ed.usage_value
            elif ed.energy_type == "heat":
                energy_heat += ed.usage_value
            elif ed.energy_type == "water":
                energy_water += ed.usage_value
            cost_total += ed.usage_value * ed.price

        energy_total = energy_electricity + energy_gas + energy_heat + energy_water

        carbon_total = (
            energy_electricity * get_carbon_factor("electricity")
            + energy_gas * get_carbon_factor("gas")
            + energy_heat * get_carbon_factor("heat")
            + energy_water * get_carbon_factor("water")
        )

        quota = (
            db.query(Quota)
            .filter(
                Quota.enterprise_id == ent.id,
                Quota.energy_type == "electricity",
                Quota.start_date <= start_date,
                Quota.end_date >= (end_date - timedelta(days=1)),
            )
            .first()
        )
        quota_usage_rate = 0.0
        if quota and quota.quota_value > 0:
            quota_usage_rate = round((energy_electricity / quota.quota_value) * 100, 2)

        suggestions_list = []
        if quota_usage_rate > 90:
            suggestions_list.append("用电已接近或超过定额，建议优化用电方案，考虑节能改造。")
        if energy_electricity > 0 and (energy_heat + energy_gas) > 0:
            suggestions_list.append("建议优化能源结构，提高清洁能源使用比例。")
        if ent.occupied_area and ent.occupied_area > 0:
            per_area = energy_total / ent.occupied_area
            if per_area > 100:
                suggestions_list.append(f"单位面积能耗{per_area:.2f}kWh/m²偏高，建议排查高能耗设备。")
        if not suggestions_list:
            suggestions_list.append("能源使用状况良好，继续保持。")

        analysis = (
            f"{report_in.report_month}月度能耗分析：总能耗{energy_total:.2f}单位，"
            f"其中电耗{energy_electricity:.2f}kWh，气耗{energy_gas:.2f}单位，"
            f"热耗{energy_heat:.2f}单位，水耗{energy_water:.2f}单位。"
            f"碳排放总量{carbon_total:.2f}kgCO₂，费用总计{cost_total:.2f}元。"
            f"定额使用率{quota_usage_rate:.2f}%。"
        )

        enterprise_stats.append(
            {
                "enterprise_id": ent.id,
                "enterprise_name": ent.name,
                "energy_total": energy_total,
                "energy_electricity": energy_electricity,
                "carbon_total": carbon_total,
                "cost_total": cost_total,
            }
        )

        existing_report = (
            db.query(MonthlyReport)
            .filter(
                MonthlyReport.enterprise_id == ent.id,
                MonthlyReport.report_month == report_in.report_month,
            )
            .first()
        )

        if existing_report:
            existing_report.energy_total = energy_total
            existing_report.energy_electricity = energy_electricity
            existing_report.energy_gas = energy_gas
            existing_report.energy_heat = energy_heat
            existing_report.energy_water = energy_water
            existing_report.carbon_total = carbon_total
            existing_report.cost_total = cost_total
            existing_report.quota_usage_rate = quota_usage_rate
            existing_report.analysis = analysis
            existing_report.suggestions = "；".join(suggestions_list)
            report_id = existing_report.id
        else:
            new_report = MonthlyReport(
                enterprise_id=ent.id,
                report_month=report_in.report_month,
                energy_total=energy_total,
                energy_electricity=energy_electricity,
                energy_gas=energy_gas,
                energy_heat=energy_heat,
                energy_water=energy_water,
                carbon_total=carbon_total,
                cost_total=cost_total,
                quota_usage_rate=quota_usage_rate,
                analysis=analysis,
                suggestions="；".join(suggestions_list),
            )
            db.add(new_report)
            db.flush()
            report_id = new_report.id

        generated_reports.append({"id": report_id, "enterprise_id": ent.id})

    enterprise_stats.sort(key=lambda x: x["energy_total"], reverse=True)
    for rank, stat in enumerate(enterprise_stats, 1):
        report = (
            db.query(MonthlyReport)
            .filter(
                MonthlyReport.enterprise_id == stat["enterprise_id"],
                MonthlyReport.report_month == report_in.report_month,
            )
            .first()
        )
        if report:
            report.ranking = rank

    db.commit()

    return GenericResponse(
        code=200,
        message=f"月度报告生成完成，共{len(generated_reports)}份",
        data={
            "report_month": report_in.report_month,
            "count": len(generated_reports),
            "items": generated_reports,
        },
    )


@router.get("/reports/monthly", response_model=GenericResponse)
def list_monthly_reports(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    report_month: Optional[str] = Query(None, description="报告月份，格式YYYY-MM"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(MonthlyReport).join(Enterprise, MonthlyReport.enterprise_id == Enterprise.id)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(MonthlyReport.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(MonthlyReport.enterprise_id == enterprise_id)

    if report_month:
        query = query.filter(MonthlyReport.report_month == report_month)

    total = query.count()
    items = query.order_by(MonthlyReport.generated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "enterprise_name": item.enterprise.name if item.enterprise else None,
            "report_month": item.report_month,
            "energy_total": item.energy_total,
            "energy_electricity": item.energy_electricity,
            "energy_gas": item.energy_gas,
            "energy_heat": item.energy_heat,
            "energy_water": item.energy_water,
            "carbon_total": item.carbon_total,
            "cost_total": item.cost_total,
            "quota_usage_rate": item.quota_usage_rate,
            "ranking": item.ranking,
            "generated_at": item.generated_at,
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


@router.get("/reports/monthly/{report_id}", response_model=GenericResponse)
def get_monthly_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if current_user.role == "enterprise_user" and current_user.enterprise_id != report.enterprise_id:
        raise HTTPException(status_code=403, detail="无权查看该报告")

    data = {
        "id": report.id,
        "enterprise_id": report.enterprise_id,
        "enterprise_name": report.enterprise.name if report.enterprise else None,
        "report_month": report.report_month,
        "energy_total": report.energy_total,
        "energy_electricity": report.energy_electricity,
        "energy_gas": report.energy_gas,
        "energy_heat": report.energy_heat,
        "energy_water": report.energy_water,
        "carbon_total": report.carbon_total,
        "cost_total": report.cost_total,
        "quota_usage_rate": report.quota_usage_rate,
        "ranking": report.ranking,
        "analysis": report.analysis,
        "suggestions": report.suggestions,
        "generated_at": report.generated_at,
    }

    return GenericResponse(code=200, message="success", data=data)


@router.post("/enterprises/ranking", response_model=GenericResponse)
def get_enterprise_ranking(
    ranking_in: EnterpriseRankingQuery,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sort_field = ranking_in.sort_by or "energy_total"
    valid_sort_fields = [
        "energy_total",
        "energy_electricity",
        "carbon_total",
        "cost_total",
        "per_area_energy",
        "per_capita_energy",
    ]
    if sort_field not in valid_sort_fields:
        raise HTTPException(status_code=400, detail=f"排序字段必须是 {', '.join(valid_sort_fields)}")

    order = ranking_in.order or "asc"
    if order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="排序方式必须是 asc 或 desc")

    limit = ranking_in.limit or 20

    query = db.query(MonthlyReport).join(Enterprise, MonthlyReport.enterprise_id == Enterprise.id)
    if ranking_in.report_month:
        query = query.filter(MonthlyReport.report_month == ranking_in.report_month)
    else:
        latest_month = db.query(func.max(MonthlyReport.report_month)).scalar()
        if latest_month:
            query = query.filter(MonthlyReport.report_month == latest_month)

    reports = query.all()
    if not reports:
        return GenericResponse(code=200, message="暂无排名数据", data={"items": []})

    ranking_items = []
    for report in reports:
        ent = report.enterprise
        per_area_energy = None
        per_capita_energy = None
        if ent and ent.occupied_area and ent.occupied_area > 0:
            per_area_energy = round(report.energy_total / ent.occupied_area, 4)
        if ent and ent.employee_count and ent.employee_count > 0:
            per_capita_energy = round(report.energy_total / ent.employee_count, 4)

        ranking_items.append(
            {
                "enterprise_id": report.enterprise_id,
                "enterprise_name": ent.name if ent else None,
                "energy_total": report.energy_total,
                "energy_electricity": report.energy_electricity,
                "carbon_total": report.carbon_total,
                "cost_total": report.cost_total,
                "quota_usage_rate": report.quota_usage_rate,
                "per_capita_energy": per_capita_energy,
                "per_area_energy": per_area_energy,
            }
        )

    reverse = (order == "desc")
    ranking_items.sort(
        key=lambda x: x.get(sort_field, 0) if x.get(sort_field) is not None else 0,
        reverse=reverse,
    )

    for i, item in enumerate(ranking_items[:limit], 1):
        item["rank"] = i

    return GenericResponse(
        code=200,
        message="success",
        data={
            "report_month": ranking_in.report_month,
            "sort_by": sort_field,
            "order": order,
            "count": min(len(ranking_items), limit),
            "items": ranking_items[:limit],
        },
    )


@router.post("/alarms", response_model=GenericResponse)
def create_alarm(
    alarm_in: AlarmCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    if alarm_in.enterprise_id:
        enterprise = db.query(Enterprise).filter(Enterprise.id == alarm_in.enterprise_id).first()
        if not enterprise:
            raise HTTPException(status_code=404, detail="企业不存在")

    alarm = Alarm(**alarm_in.model_dump())
    db.add(alarm)
    db.commit()
    db.refresh(alarm)

    return GenericResponse(
        code=201,
        message="告警创建成功",
        data={"id": alarm.id},
    )


@router.get("/alarms", response_model=GenericResponse)
def list_alarms(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    alarm_type: Optional[str] = Query(None, description="告警类型"),
    level: Optional[str] = Query(None, description="告警级别"),
    status: Optional[str] = Query(None, description="告警状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Alarm).outerjoin(Enterprise, Alarm.enterprise_id == Enterprise.id)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(Alarm.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(Alarm.enterprise_id == enterprise_id)

    if alarm_type:
        query = query.filter(Alarm.alarm_type == alarm_type)
    if level:
        query = query.filter(Alarm.level == level)
    if status:
        query = query.filter(Alarm.status == status)

    total = query.count()
    items = query.order_by(Alarm.alarm_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "enterprise_name": item.enterprise.name if item.enterprise else None,
            "alarm_type": item.alarm_type,
            "energy_type": item.energy_type,
            "level": item.level,
            "title": item.title,
            "content": item.content,
            "value": item.value,
            "threshold": item.threshold,
            "status": item.status,
            "alarm_time": item.alarm_time,
            "processed_time": item.processed_time,
            "processed_by": item.processed_by,
            "remark": item.remark,
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


@router.get("/alarms/{alarm_id}", response_model=GenericResponse)
def get_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    if current_user.role == "enterprise_user" and current_user.enterprise_id != alarm.enterprise_id:
        raise HTTPException(status_code=403, detail="无权查看该告警")

    data = {
        "id": alarm.id,
        "enterprise_id": alarm.enterprise_id,
        "enterprise_name": alarm.enterprise.name if alarm.enterprise else None,
        "alarm_type": alarm.alarm_type,
        "energy_type": alarm.energy_type,
        "level": alarm.level,
        "title": alarm.title,
        "content": alarm.content,
        "value": alarm.value,
        "threshold": alarm.threshold,
        "status": alarm.status,
        "alarm_time": alarm.alarm_time,
        "processed_time": alarm.processed_time,
        "processed_by": alarm.processed_by,
        "remark": alarm.remark,
        "created_at": alarm.created_at,
    }

    return GenericResponse(code=200, message="success", data=data)


@router.put("/alarms/{alarm_id}", response_model=GenericResponse)
def process_alarm(
    alarm_id: int,
    alarm_in: AlarmUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager", "enterprise_user")),
):
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    if current_user.role == "enterprise_user" and current_user.enterprise_id != alarm.enterprise_id:
        raise HTTPException(status_code=403, detail="无权处理该告警")

    update_data = alarm_in.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] != alarm.status and alarm.status != "processed":
        update_data["processed_time"] = datetime.utcnow()
        update_data["processed_by"] = current_user.username

    for key, value in update_data.items():
        setattr(alarm, key, value)

    db.commit()
    db.refresh(alarm)

    return GenericResponse(
        code=200,
        message="告警处理成功",
        data={
            "id": alarm.id,
            "status": alarm.status,
            "processed_by": alarm.processed_by,
            "processed_time": alarm.processed_time,
        },
    )


@router.post("/subscriptions", response_model=GenericResponse)
def create_subscription(
    subscription_in: AlertSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "enterprise_user":
        if subscription_in.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能为自己创建订阅")
    else:
        user = db.query(User).filter(User.id == subscription_in.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

    existing = (
        db.query(AlertSubscription)
        .filter(
            AlertSubscription.user_id == subscription_in.user_id,
            AlertSubscription.alarm_type == subscription_in.alarm_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该用户已订阅此告警类型")

    subscription = AlertSubscription(**subscription_in.model_dump())
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return GenericResponse(
        code=201,
        message="订阅创建成功",
        data={"id": subscription.id},
    )


@router.get("/subscriptions", response_model=GenericResponse)
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(AlertSubscription).join(User, AlertSubscription.user_id == User.id)

    if current_user.role == "enterprise_user":
        query = query.filter(AlertSubscription.user_id == current_user.id)

    items = query.order_by(AlertSubscription.created_at.desc()).all()

    data = [
        {
            "id": item.id,
            "user_id": item.user_id,
            "username": item.user.username if item.user else None,
            "alarm_type": item.alarm_type,
            "notify_email": item.notify_email,
            "notify_sms": item.notify_sms,
            "notify_wechat": item.notify_wechat,
            "enabled": item.enabled,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in items
    ]

    return GenericResponse(
        code=200,
        message="success",
        data={"count": len(data), "items": data},
    )


@router.put("/subscriptions/{subscription_id}", response_model=GenericResponse)
def update_subscription(
    subscription_id: int,
    subscription_in: AlertSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    subscription = db.query(AlertSubscription).filter(AlertSubscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="订阅不存在")

    if current_user.role == "enterprise_user" and subscription.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改该订阅")

    update_data = subscription_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subscription, key, value)

    db.commit()
    db.refresh(subscription)

    return GenericResponse(
        code=200,
        message="订阅更新成功",
        data={
            "id": subscription.id,
            "enabled": subscription.enabled,
            "notify_email": subscription.notify_email,
            "notify_sms": subscription.notify_sms,
            "notify_wechat": subscription.notify_wechat,
        },
    )


@router.delete("/subscriptions/{subscription_id}", response_model=GenericResponse)
def delete_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    subscription = db.query(AlertSubscription).filter(AlertSubscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="订阅不存在")

    if current_user.role == "enterprise_user" and subscription.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除该订阅")

    db.delete(subscription)
    db.commit()

    return GenericResponse(
        code=200,
        message="订阅删除成功",
        data={"id": subscription_id},
    )
