from datetime import datetime, timedelta, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import get_db
from app.models.models import Quota, AbnormalUsage, EnergyData, Enterprise
from app.schemas.schemas import (
    QuotaCreate,
    QuotaUpdate,
    QuotaResponse,
    QuotaUsage,
    AbnormalDetectQuery,
    AbnormalUsageResponse,
    AbnormalUsageUpdate,
    GenericResponse,
)
from app.utils.auth import get_current_user, require_roles

router = APIRouter(prefix="", tags=["定额与异常用电"])


@router.post("/quotas", response_model=QuotaResponse, status_code=status.HTTP_201_CREATED)
def create_quota(
    quota_in: QuotaCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    enterprise = db.query(Enterprise).filter(Enterprise.id == quota_in.enterprise_id).first()
    if not enterprise:
        raise HTTPException(status_code=404, detail="企业不存在")

    if quota_in.start_date >= quota_in.end_date:
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    existing = (
        db.query(Quota)
        .filter(
            Quota.enterprise_id == quota_in.enterprise_id,
            Quota.energy_type == quota_in.energy_type,
            and_(
                Quota.start_date <= quota_in.end_date,
                Quota.end_date >= quota_in.start_date,
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该企业该能源类型在指定时间段内已有定额")

    db_quota = Quota(**quota_in.model_dump())
    db.add(db_quota)
    db.commit()
    db.refresh(db_quota)
    return db_quota


@router.get("/quotas", response_model=List[QuotaResponse])
def list_quotas(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    energy_type: Optional[str] = Query(None, description="能源类型"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Quota)
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(Quota.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(Quota.enterprise_id == enterprise_id)
    if energy_type:
        query = query.filter(Quota.energy_type == energy_type)
    return query.order_by(Quota.created_at.desc()).all()


@router.get("/quotas/usage", response_model=List[QuotaUsage])
def list_quota_usage(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    energy_type: Optional[str] = Query(None, description="能源类型"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Quota)
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(Quota.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(Quota.enterprise_id == enterprise_id)
    if energy_type:
        query = query.filter(Quota.energy_type == energy_type)

    quotas = query.all()
    result: List[QuotaUsage] = []

    for quota in quotas:
        start_dt = datetime.combine(quota.start_date, datetime.min.time())
        end_dt = datetime.combine(quota.end_date, datetime.max.time())

        used = (
            db.query(func.sum(EnergyData.usage_value))
            .filter(
                EnergyData.enterprise_id == quota.enterprise_id,
                EnergyData.energy_type == quota.energy_type,
                EnergyData.data_time >= start_dt,
                EnergyData.data_time <= end_dt,
            )
            .scalar()
            or 0.0
        )

        usage_rate = round((used / quota.quota_value) * 100, 2) if quota.quota_value > 0 else 0.0

        result.append(
            QuotaUsage(
                quota_id=quota.id,
                enterprise_id=quota.enterprise_id,
                energy_type=quota.energy_type,
                quota_value=quota.quota_value,
                used_value=used,
                usage_rate=usage_rate,
                start_date=quota.start_date,
                end_date=quota.end_date,
            )
        )
    return result


@router.get("/quotas/{quota_id}", response_model=QuotaResponse)
def get_quota(
    quota_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    quota = db.query(Quota).filter(Quota.id == quota_id).first()
    if not quota:
        raise HTTPException(status_code=404, detail="定额不存在")
    if current_user.role == "enterprise_user" and current_user.enterprise_id != quota.enterprise_id:
        raise HTTPException(status_code=403, detail="无权查看该定额")
    return quota


@router.put("/quotas/{quota_id}", response_model=QuotaResponse)
def update_quota(
    quota_id: int,
    quota_in: QuotaUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    quota = db.query(Quota).filter(Quota.id == quota_id).first()
    if not quota:
        raise HTTPException(status_code=404, detail="定额不存在")

    update_data = quota_in.model_dump(exclude_unset=True)

    if "start_date" in update_data and "end_date" in update_data:
        if update_data["start_date"] >= update_data["end_date"]:
            raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")
    elif "start_date" in update_data:
        if update_data["start_date"] >= quota.end_date:
            raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")
    elif "end_date" in update_data:
        if quota.start_date >= update_data["end_date"]:
            raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    for key, value in update_data.items():
        setattr(quota, key, value)

    db.commit()
    db.refresh(quota)
    return quota


@router.delete("/quotas/{quota_id}", response_model=GenericResponse)
def delete_quota(
    quota_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    quota = db.query(Quota).filter(Quota.id == quota_id).first()
    if not quota:
        raise HTTPException(status_code=404, detail="定额不存在")
    db.delete(quota)
    db.commit()
    return GenericResponse(code=200, message="删除成功", data={"id": quota_id})


def _detect_quota_exceed(db: Session, query_params: AbnormalDetectQuery) -> List[AbnormalUsage]:
    abnormals: List[AbnormalUsage] = []
    quota_query = db.query(Quota)
    if query_params.enterprise_id:
        quota_query = quota_query.filter(Quota.enterprise_id == query_params.enterprise_id)
    if query_params.energy_type:
        quota_query = quota_query.filter(Quota.energy_type == query_params.energy_type)

    for quota in quota_query.all():
        start_dt = datetime.combine(quota.start_date, datetime.min.time())
        end_dt = datetime.combine(quota.end_date, datetime.max.time())
        now = datetime.utcnow()
        if now < start_dt or now > end_dt:
            continue

        used = (
            db.query(func.sum(EnergyData.usage_value))
            .filter(
                EnergyData.enterprise_id == quota.enterprise_id,
                EnergyData.energy_type == quota.energy_type,
                EnergyData.data_time >= start_dt,
                EnergyData.data_time <= min(now, end_dt),
            )
            .scalar()
            or 0.0
        )

        threshold_value = quota.quota_value * (quota.warning_threshold / 100.0)
        if used >= threshold_value:
            deviation = round(((used - threshold_value) / threshold_value) * 100, 2) if threshold_value > 0 else 0.0
            existing = (
                db.query(AbnormalUsage)
                .filter(
                    AbnormalUsage.enterprise_id == quota.enterprise_id,
                    AbnormalUsage.energy_type == quota.energy_type,
                    AbnormalUsage.abnormal_type == "quota_exceed",
                    func.date(AbnormalUsage.detected_time) == date.today(),
                )
                .first()
            )
            if not existing:
                abnormal = AbnormalUsage(
                    enterprise_id=quota.enterprise_id,
                    energy_type=quota.energy_type,
                    abnormal_type="quota_exceed",
                    detected_time=now,
                    value=used,
                    expected_value=threshold_value,
                    deviation_rate=deviation,
                    description=f"用能已达定额{quota.warning_threshold}%阈值，当前用量{used}，阈值{threshold_value}",
                    status="detected",
                )
                db.add(abnormal)
                abnormals.append(abnormal)
    return abnormals


def _detect_yoy_growth(db: Session, query_params: AbnormalDetectQuery) -> List[AbnormalUsage]:
    abnormals: List[AbnormalUsage] = []
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    year_ago = now - timedelta(days=365)

    enterprise_ids = [query_params.enterprise_id] if query_params.enterprise_id else None
    if not enterprise_ids:
        enterprise_ids = [e.id for e in db.query(Enterprise.id).all()]

    energy_types = [query_params.energy_type] if query_params.energy_type else ["electricity", "gas", "heat", "water"]

    for eid in enterprise_ids:
        for etype in energy_types:
            current_usage = (
                db.query(func.sum(EnergyData.usage_value))
                .filter(
                    EnergyData.enterprise_id == eid,
                    EnergyData.energy_type == etype,
                    EnergyData.data_time >= week_ago,
                    EnergyData.data_time <= now,
                )
                .scalar()
                or 0.0
            )
            last_year_usage = (
                db.query(func.sum(EnergyData.usage_value))
                .filter(
                    EnergyData.enterprise_id == eid,
                    EnergyData.energy_type == etype,
                    EnergyData.data_time >= year_ago,
                    EnergyData.data_time <= (year_ago + timedelta(days=7)),
                )
                .scalar()
                or 0.0
            )

            if last_year_usage > 0 and current_usage > 0:
                yoy_rate = round(((current_usage - last_year_usage) / last_year_usage) * 100, 2)
                if yoy_rate >= 30.0:
                    existing = (
                        db.query(AbnormalUsage)
                        .filter(
                            AbnormalUsage.enterprise_id == eid,
                            AbnormalUsage.energy_type == etype,
                            AbnormalUsage.abnormal_type == "yoy_growth",
                            func.date(AbnormalUsage.detected_time) == date.today(),
                        )
                        .first()
                    )
                    if not existing:
                        abnormal = AbnormalUsage(
                            enterprise_id=eid,
                            energy_type=etype,
                            abnormal_type="yoy_growth",
                            detected_time=now,
                            value=current_usage,
                            expected_value=last_year_usage,
                            deviation_rate=yoy_rate,
                            description=f"同比增长{yoy_rate}%超过30%阈值，本周用量{current_usage}，去年同期{last_year_usage}",
                            status="detected",
                        )
                        db.add(abnormal)
                        abnormals.append(abnormal)
    return abnormals


def _detect_load_surge(db: Session, query_params: AbnormalDetectQuery) -> List[AbnormalUsage]:
    abnormals: List[AbnormalUsage] = []
    now = datetime.utcnow()

    enterprise_ids = [query_params.enterprise_id] if query_params.enterprise_id else None
    if not enterprise_ids:
        enterprise_ids = [e.id for e in db.query(Enterprise.id).all()]

    energy_types = [query_params.energy_type] if query_params.energy_type else ["electricity"]

    for eid in enterprise_ids:
        for etype in energy_types:
            recent_data = (
                db.query(EnergyData)
                .filter(
                    EnergyData.enterprise_id == eid,
                    EnergyData.energy_type == etype,
                    EnergyData.data_time >= (now - timedelta(hours=6)),
                )
                .order_by(EnergyData.data_time.desc())
                .limit(10)
                .all()
            )

            if len(recent_data) < 4:
                continue

            recent_data = sorted(recent_data, key=lambda x: x.data_time)
            baseline_values = [d.usage_value for d in recent_data[:-3]]
            if not baseline_values:
                continue

            baseline_avg = sum(baseline_values) / len(baseline_values)
            if baseline_avg <= 0:
                continue

            last_three = [d.usage_value for d in recent_data[-3:]]
            surge_count = sum(1 for v in last_three if v >= baseline_avg * 1.5)

            if surge_count >= 3:
                avg_last_three = sum(last_three) / 3
                deviation = round(((avg_last_three - baseline_avg) / baseline_avg) * 100, 2)
                existing = (
                    db.query(AbnormalUsage)
                    .filter(
                        AbnormalUsage.enterprise_id == eid,
                        AbnormalUsage.energy_type == etype,
                        AbnormalUsage.abnormal_type == "load_surge",
                        func.date(AbnormalUsage.detected_time) == date.today(),
                    )
                    .first()
                )
                if not existing:
                    abnormal = AbnormalUsage(
                        enterprise_id=eid,
                        energy_type=etype,
                        abnormal_type="load_surge",
                        detected_time=now,
                        value=avg_last_three,
                        expected_value=baseline_avg,
                        deviation_rate=deviation,
                        description=f"连续3小时负荷突增，最近3小时均值{avg_last_three:.2f}，基准值{baseline_avg:.2f}，偏差{deviation}%",
                        status="detected",
                    )
                    db.add(abnormal)
                    abnormals.append(abnormal)
    return abnormals


@router.post("/abnormal/detect", response_model=GenericResponse)
def detect_abnormal(
    query_params: AbnormalDetectQuery,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager", "enterprise_user")),
):
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query_params.enterprise_id = current_user.enterprise_id

    abnormals: List[AbnormalUsage] = []

    if not query_params.abnormal_type or query_params.abnormal_type == "quota_exceed":
        abnormals.extend(_detect_quota_exceed(db, query_params))

    if not query_params.abnormal_type or query_params.abnormal_type == "yoy_growth":
        abnormals.extend(_detect_yoy_growth(db, query_params))

    if not query_params.abnormal_type or query_params.abnormal_type == "load_surge":
        abnormals.extend(_detect_load_surge(db, query_params))

    db.commit()
    for a in abnormals:
        db.refresh(a)

    return GenericResponse(
        code=200,
        message=f"检测完成，发现{len(abnormals)}条异常记录",
        data={"count": len(abnormals), "types": list(set([a.abnormal_type for a in abnormals]))},
    )


@router.get("/abnormal", response_model=List[AbnormalUsageResponse])
def list_abnormal(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    energy_type: Optional[str] = Query(None, description="能源类型"),
    abnormal_type: Optional[str] = Query(None, description="异常类型"),
    status: Optional[str] = Query(None, description="处理状态"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(AbnormalUsage)
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(AbnormalUsage.enterprise_id == current_user.enterprise_id)
    elif enterprise_id is not None:
        query = query.filter(AbnormalUsage.enterprise_id == enterprise_id)
    if energy_type:
        query = query.filter(AbnormalUsage.energy_type == energy_type)
    if abnormal_type:
        query = query.filter(AbnormalUsage.abnormal_type == abnormal_type)
    if status:
        query = query.filter(AbnormalUsage.status == status)
    if start_time:
        query = query.filter(AbnormalUsage.detected_time >= start_time)
    if end_time:
        query = query.filter(AbnormalUsage.detected_time <= end_time)

    return query.order_by(AbnormalUsage.detected_time.desc()).offset(skip).limit(limit).all()


@router.get("/abnormal/{abnormal_id}", response_model=AbnormalUsageResponse)
def get_abnormal(
    abnormal_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    abnormal = db.query(AbnormalUsage).filter(AbnormalUsage.id == abnormal_id).first()
    if not abnormal:
        raise HTTPException(status_code=404, detail="异常记录不存在")
    if current_user.role == "enterprise_user" and current_user.enterprise_id != abnormal.enterprise_id:
        raise HTTPException(status_code=403, detail="无权查看该记录")
    return abnormal


@router.put("/abnormal/{abnormal_id}", response_model=AbnormalUsageResponse)
def update_abnormal(
    abnormal_id: int,
    abnormal_in: AbnormalUsageUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager", "enterprise_user")),
):
    abnormal = db.query(AbnormalUsage).filter(AbnormalUsage.id == abnormal_id).first()
    if not abnormal:
        raise HTTPException(status_code=404, detail="异常记录不存在")
    if current_user.role == "enterprise_user" and current_user.enterprise_id != abnormal.enterprise_id:
        raise HTTPException(status_code=403, detail="无权处理该记录")

    update_data = abnormal_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != abnormal.status:
        update_data["handled_at"] = datetime.utcnow()
        update_data["handled_by"] = current_user.username

    for key, value in update_data.items():
        setattr(abnormal, key, value)

    db.commit()
    db.refresh(abnormal)
    return abnormal
