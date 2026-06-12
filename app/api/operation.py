from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db
from app.config import settings
from app.models.models import (
    DeviceRecord,
    SavingSuggestion,
    DemandResponseEvent,
    DemandResponse,
    Building,
    Enterprise,
    EnergyData,
    Quota,
)
from app.schemas.schemas import (
    DeviceRecordCreate,
    DeviceRecordResponse,
    SavingSuggestionGenerate,
    SavingSuggestionResponse,
    SavingSuggestionUpdate,
    DemandResponseEventCreate,
    DemandResponseEventResponse,
    DemandResponseEventUpdate,
    DemandResponseCreate,
    DemandResponseResponse,
    DemandResponseUpdate,
    DemandResponseEffect,
    GenericResponse,
)
from app.utils.auth import get_current_user, require_roles

router = APIRouter(prefix="", tags=["运营管理"])


@router.post("/devices/records", response_model=GenericResponse)
def create_device_record(
    data_in: DeviceRecordCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    if data_in.building_id:
        building = db.query(Building).filter(Building.id == data_in.building_id).first()
        if not building:
            raise HTTPException(status_code=404, detail="楼栋不存在")

    record = DeviceRecord(**data_in.model_dump())
    if not record.operator:
        record.operator = current_user.username
    db.add(record)
    db.commit()
    db.refresh(record)

    return GenericResponse(
        code=201,
        message="设备停启记录创建成功",
        data={"id": record.id},
    )


@router.get("/devices/records", response_model=GenericResponse)
def get_device_records(
    building_id: Optional[int] = Query(None, description="楼栋ID"),
    device_name: Optional[str] = Query(None, description="设备名称"),
    device_code: Optional[str] = Query(None, description="设备编号"),
    action_type: Optional[str] = Query(None, description="操作类型"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(DeviceRecord)

    if building_id:
        query = query.filter(DeviceRecord.building_id == building_id)
    if device_name:
        query = query.filter(DeviceRecord.device_name.contains(device_name))
    if device_code:
        query = query.filter(DeviceRecord.device_code == device_code)
    if action_type:
        query = query.filter(DeviceRecord.action_type == action_type)
    if start_time:
        query = query.filter(DeviceRecord.action_time >= start_time)
    if end_time:
        query = query.filter(DeviceRecord.action_time <= end_time)

    total = query.count()
    items = query.order_by(DeviceRecord.action_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "building_id": item.building_id,
            "device_name": item.device_name,
            "device_code": item.device_code,
            "action_type": item.action_type,
            "operator": item.operator,
            "action_time": item.action_time,
            "reason": item.reason,
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


@router.get("/devices/records/{record_id}", response_model=GenericResponse)
def get_device_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    record = db.query(DeviceRecord).filter(DeviceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="设备停启记录不存在")

    data = {
        "id": record.id,
        "building_id": record.building_id,
        "device_name": record.device_name,
        "device_code": record.device_code,
        "action_type": record.action_type,
        "operator": record.operator,
        "action_time": record.action_time,
        "reason": record.reason,
        "remark": record.remark,
        "created_at": record.created_at,
    }

    return GenericResponse(
        code=200,
        message="success",
        data=data,
    )


@router.post("/suggestions/generate", response_model=GenericResponse)
def generate_suggestions(
    query_in: SavingSuggestionGenerate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager", "enterprise_user")),
):
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        enterprise_ids = [current_user.enterprise_id]
    elif query_in.enterprise_id:
        enterprise_ids = [query_in.enterprise_id]
    else:
        enterprise_ids = [e.id for e in db.query(Enterprise.id).all()]

    generated: List[SavingSuggestion] = []
    now = datetime.utcnow()

    for eid in enterprise_ids:
        enterprise = db.query(Enterprise).filter(Enterprise.id == eid).first()
        if not enterprise:
            continue

        if not query_in.suggestion_type or query_in.suggestion_type == "temperature":
            suggestion = SavingSuggestion(
                enterprise_id=eid,
                suggestion_type="temperature",
                title="空调温度设置优化",
                content="建议夏季将空调温度设置在26℃以上，冬季设置在20℃以下。每提高/降低1℃可节能约6%-8%。同时建议合理设置空调运行时间，非工作时段及时关闭。",
                potential_saving=8.0,
                saving_unit="%",
                priority="high",
                status="new",
                generated_at=now,
            )
            db.add(suggestion)
            generated.append(suggestion)

        if not query_in.suggestion_type or query_in.suggestion_type == "lighting":
            suggestion = SavingSuggestion(
                enterprise_id=eid,
                suggestion_type="lighting",
                title="照明改造建议",
                content="建议将传统照明设备更换为LED节能灯具，可节能约50%-70%。同时建议安装智能照明控制系统，实现人来灯亮、人走灯灭，充分利用自然光。",
                potential_saving=60.0,
                saving_unit="%",
                priority="medium",
                status="new",
                generated_at=now,
            )
            db.add(suggestion)
            generated.append(suggestion)

        if not query_in.suggestion_type or query_in.suggestion_type == "peak_valley":
            thirty_days_ago = now - timedelta(days=30)
            peak_usage = (
                db.query(func.sum(EnergyData.usage_value))
                .filter(
                    EnergyData.enterprise_id == eid,
                    EnergyData.energy_type == "electricity",
                    EnergyData.peak_type == "peak",
                    EnergyData.data_time >= thirty_days_ago,
                )
                .scalar()
                or 0.0
            )
            total_usage = (
                db.query(func.sum(EnergyData.usage_value))
                .filter(
                    EnergyData.enterprise_id == eid,
                    EnergyData.energy_type == "electricity",
                    EnergyData.data_time >= thirty_days_ago,
                )
                .scalar()
                or 0.0
            )
            peak_ratio = round((peak_usage / total_usage) * 100, 2) if total_usage > 0 else 0
            if peak_ratio > 40:
                suggestion = SavingSuggestion(
                    enterprise_id=eid,
                    suggestion_type="peak_valley",
                    title="峰谷用电优化",
                    content=f"近30天峰时用电占比达{peak_ratio}%，高于建议值40%。建议将部分可调整负荷（如设备充电、储能充电等）转移至谷时段，降低用电成本。峰谷电价比约为3:1，优化后预计可节省电费约15%-25%。",
                    potential_saving=20.0,
                    saving_unit="%",
                    priority="high",
                    status="new",
                    generated_at=now,
                )
                db.add(suggestion)
                generated.append(suggestion)

        if not query_in.suggestion_type or query_in.suggestion_type == "quota":
            active_quotas = (
                db.query(Quota)
                .filter(
                    Quota.enterprise_id == eid,
                    Quota.start_date <= now.date(),
                    Quota.end_date >= now.date(),
                )
                .all()
            )
            for quota in active_quotas:
                start_dt = datetime.combine(quota.start_date, datetime.min.time())
                end_dt = min(datetime.combine(quota.end_date, datetime.max.time()), now)
                used = (
                    db.query(func.sum(EnergyData.usage_value))
                    .filter(
                        EnergyData.enterprise_id == eid,
                        EnergyData.energy_type == quota.energy_type,
                        EnergyData.data_time >= start_dt,
                        EnergyData.data_time <= end_dt,
                    )
                    .scalar()
                    or 0.0
                )
                usage_rate = round((used / quota.quota_value) * 100, 2) if quota.quota_value > 0 else 0
                if usage_rate >= 80:
                    suggestion = SavingSuggestion(
                        enterprise_id=eid,
                        suggestion_type="quota",
                        title=f"{quota.energy_type}能耗定额预警",
                        content=f"当前{quota.energy_type}能耗已达定额的{usage_rate}%，定额值{quota.quota_value}，已使用{used}。建议立即采取节能措施，如关闭非必要设备、优化运行策略等，避免超定额运行。",
                        potential_saving=usage_rate - 80,
                        saving_unit="%",
                        priority="high",
                        status="new",
                        generated_at=now,
                    )
                    db.add(suggestion)
                    generated.append(suggestion)

        if not query_in.suggestion_type or query_in.suggestion_type == "maintenance":
            suggestion = SavingSuggestion(
                enterprise_id=eid,
                suggestion_type="maintenance",
                title="设备维护建议",
                content="建议定期对主要用能设备（空调、空压机、水泵等）进行维护保养：1) 每月清洁空调滤网，可提高换热效率10%-15%；2) 每季度检查设备管道泄漏情况；3) 每年进行设备能效检测，及时淘汰低能效设备。",
                potential_saving=15.0,
                saving_unit="%",
                priority="medium",
                status="new",
                generated_at=now,
            )
            db.add(suggestion)
            generated.append(suggestion)

    db.commit()
    for s in generated:
        db.refresh(s)

    return GenericResponse(
        code=200,
        message=f"节能建议生成完成，共生成{len(generated)}条建议",
        data={
            "count": len(generated),
            "ids": [s.id for s in generated],
        },
    )


@router.get("/suggestions", response_model=GenericResponse)
def get_suggestions(
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    suggestion_type: Optional[str] = Query(None, description="建议类型"),
    priority: Optional[str] = Query(None, description="优先级"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(SavingSuggestion)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(SavingSuggestion.enterprise_id == current_user.enterprise_id)
    elif enterprise_id:
        query = query.filter(SavingSuggestion.enterprise_id == enterprise_id)

    if suggestion_type:
        query = query.filter(SavingSuggestion.suggestion_type == suggestion_type)
    if priority:
        query = query.filter(SavingSuggestion.priority == priority)
    if status:
        query = query.filter(SavingSuggestion.status == status)

    total = query.count()
    items = query.order_by(SavingSuggestion.generated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "enterprise_id": item.enterprise_id,
            "suggestion_type": item.suggestion_type,
            "title": item.title,
            "content": item.content,
            "potential_saving": item.potential_saving,
            "saving_unit": item.saving_unit,
            "priority": item.priority,
            "status": item.status,
            "generated_at": item.generated_at,
            "handled_by": item.handled_by,
            "handled_at": item.handled_at,
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


@router.get("/suggestions/{suggestion_id}", response_model=GenericResponse)
def get_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    suggestion = db.query(SavingSuggestion).filter(SavingSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="节能建议不存在")
    if current_user.role == "enterprise_user" and current_user.enterprise_id != suggestion.enterprise_id:
        raise HTTPException(status_code=403, detail="无权查看该建议")

    data = {
        "id": suggestion.id,
        "enterprise_id": suggestion.enterprise_id,
        "suggestion_type": suggestion.suggestion_type,
        "title": suggestion.title,
        "content": suggestion.content,
        "potential_saving": suggestion.potential_saving,
        "saving_unit": suggestion.saving_unit,
        "priority": suggestion.priority,
        "status": suggestion.status,
        "generated_at": suggestion.generated_at,
        "handled_by": suggestion.handled_by,
        "handled_at": suggestion.handled_at,
        "remark": suggestion.remark,
        "created_at": suggestion.created_at,
    }

    return GenericResponse(
        code=200,
        message="success",
        data=data,
    )


@router.put("/suggestions/{suggestion_id}", response_model=GenericResponse)
def handle_suggestion(
    suggestion_id: int,
    data_in: SavingSuggestionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    suggestion = db.query(SavingSuggestion).filter(SavingSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="节能建议不存在")
    if current_user.role == "enterprise_user" and current_user.enterprise_id != suggestion.enterprise_id:
        raise HTTPException(status_code=403, detail="无权处理该建议")

    update_data = data_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != suggestion.status:
        update_data["handled_at"] = datetime.utcnow()
        update_data["handled_by"] = current_user.username

    for key, value in update_data.items():
        setattr(suggestion, key, value)

    db.commit()
    db.refresh(suggestion)

    return GenericResponse(
        code=200,
        message="节能建议处理成功",
        data={"id": suggestion.id},
    )


@router.post("/demand/events", response_model=GenericResponse)
def create_demand_event(
    data_in: DemandResponseEventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager")),
):
    if data_in.start_time >= data_in.end_time:
        raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")

    event = DemandResponseEvent(**data_in.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)

    return GenericResponse(
        code=201,
        message="需求响应事件创建成功",
        data={"id": event.id},
    )


@router.get("/demand/events", response_model=GenericResponse)
def get_demand_events(
    response_type: Optional[str] = Query(None, description="响应类型"),
    status: Optional[str] = Query(None, description="状态"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(DemandResponseEvent)

    if response_type:
        query = query.filter(DemandResponseEvent.response_type == response_type)
    if status:
        query = query.filter(DemandResponseEvent.status == status)
    if start_time:
        query = query.filter(DemandResponseEvent.start_time >= start_time)
    if end_time:
        query = query.filter(DemandResponseEvent.end_time <= end_time)

    total = query.count()
    items = query.order_by(DemandResponseEvent.start_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "event_code": item.event_code,
            "event_name": item.event_name,
            "response_type": item.response_type,
            "start_time": item.start_time,
            "end_time": item.end_time,
            "target_load": item.target_load,
            "status": item.status,
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


@router.get("/demand/events/{event_id}", response_model=GenericResponse)
def get_demand_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    event = db.query(DemandResponseEvent).filter(DemandResponseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="需求响应事件不存在")

    data = {
        "id": event.id,
        "event_code": event.event_code,
        "event_name": event.event_name,
        "response_type": event.response_type,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "target_load": event.target_load,
        "status": event.status,
        "description": event.description,
        "created_at": event.created_at,
    }

    return GenericResponse(
        code=200,
        message="success",
        data=data,
    )


@router.put("/demand/events/{event_id}", response_model=GenericResponse)
def update_demand_event(
    event_id: int,
    data_in: DemandResponseEventUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager")),
):
    event = db.query(DemandResponseEvent).filter(DemandResponseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="需求响应事件不存在")

    update_data = data_in.model_dump(exclude_unset=True)

    if "start_time" in update_data and "end_time" in update_data:
        if update_data["start_time"] >= update_data["end_time"]:
            raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
    elif "start_time" in update_data:
        if update_data["start_time"] >= event.end_time:
            raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
    elif "end_time" in update_data:
        if event.start_time >= update_data["end_time"]:
            raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")

    for key, value in update_data.items():
        setattr(event, key, value)

    db.commit()
    db.refresh(event)

    return GenericResponse(
        code=200,
        message="需求响应事件更新成功",
        data={"id": event.id},
    )


@router.post("/demand/signup", response_model=GenericResponse)
def signup_demand_response(
    data_in: DemandResponseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        if current_user.enterprise_id != data_in.enterprise_id:
            raise HTTPException(status_code=403, detail="仅能为所在企业报名")
    elif data_in.enterprise_id:
        enterprise = db.query(Enterprise).filter(Enterprise.id == data_in.enterprise_id).first()
        if not enterprise:
            raise HTTPException(status_code=404, detail="企业不存在")

    event = db.query(DemandResponseEvent).filter(DemandResponseEvent.id == data_in.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="需求响应事件不存在")
    if event.status != "open":
        raise HTTPException(status_code=400, detail="该事件不接受报名")

    existing = (
        db.query(DemandResponse)
        .filter(
            DemandResponse.event_id == data_in.event_id,
            DemandResponse.enterprise_id == data_in.enterprise_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该企业已报名此事件")

    response = DemandResponse(
        event_id=data_in.event_id,
        enterprise_id=data_in.enterprise_id,
        signed_up=True,
        committed_load=data_in.committed_load,
        status="signed",
        signed_at=datetime.utcnow(),
    )
    db.add(response)
    db.commit()
    db.refresh(response)

    return GenericResponse(
        code=201,
        message="需求响应报名成功",
        data={"id": response.id},
    )


@router.get("/demand/responses", response_model=GenericResponse)
def get_demand_responses(
    event_id: Optional[int] = Query(None, description="事件ID"),
    enterprise_id: Optional[int] = Query(None, description="企业ID"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(DemandResponse)

    if current_user.role == "enterprise_user" and current_user.enterprise_id:
        query = query.filter(DemandResponse.enterprise_id == current_user.enterprise_id)
    elif enterprise_id:
        query = query.filter(DemandResponse.enterprise_id == enterprise_id)

    if event_id:
        query = query.filter(DemandResponse.event_id == event_id)
    if status:
        query = query.filter(DemandResponse.status == status)

    total = query.count()
    items = query.order_by(DemandResponse.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    data = [
        {
            "id": item.id,
            "event_id": item.event_id,
            "enterprise_id": item.enterprise_id,
            "signed_up": item.signed_up,
            "committed_load": item.committed_load,
            "actual_load": item.actual_load,
            "baseline_load": item.baseline_load,
            "effect_load": item.effect_load,
            "incentive_amount": item.incentive_amount,
            "status": item.status,
            "signed_at": item.signed_at,
            "verified_at": item.verified_at,
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


@router.put("/demand/responses/{response_id}", response_model=GenericResponse)
def update_demand_response(
    response_id: int,
    data_in: DemandResponseUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    response = db.query(DemandResponse).filter(DemandResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="报名记录不存在")

    update_data = data_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != response.status:
        if update_data["status"] in ["verified", "settled"]:
            update_data["verified_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(response, key, value)

    db.commit()
    db.refresh(response)

    return GenericResponse(
        code=200,
        message="报名信息更新成功",
        data={"id": response.id},
    )


@router.post("/demand/calculate-effect", response_model=GenericResponse)
def calculate_demand_effect(
    event_id: int = Query(..., description="事件ID"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "park_manager", "property_manager")),
):
    event = db.query(DemandResponseEvent).filter(DemandResponseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="需求响应事件不存在")

    responses = (
        db.query(DemandResponse)
        .filter(
            DemandResponse.event_id == event_id,
            DemandResponse.signed_up == True,
        )
        .all()
    )

    results: List[dict] = []
    event_duration = (event.end_time - event.start_time).total_seconds() / 3600
    baseline_start = event.start_time - timedelta(days=7)
    baseline_end = event.end_time - timedelta(days=7)

    for resp in responses:
        enterprise = db.query(Enterprise).filter(Enterprise.id == resp.enterprise_id).first()
        if not enterprise:
            continue

        actual_load = (
            db.query(func.sum(EnergyData.usage_value))
            .filter(
                EnergyData.enterprise_id == resp.enterprise_id,
                EnergyData.energy_type == "electricity",
                EnergyData.data_time >= event.start_time,
                EnergyData.data_time <= event.end_time,
            )
            .scalar()
            or 0.0
        )

        baseline_load = (
            db.query(func.sum(EnergyData.usage_value))
            .filter(
                EnergyData.enterprise_id == resp.enterprise_id,
                EnergyData.energy_type == "electricity",
                EnergyData.data_time >= baseline_start,
                EnergyData.data_time <= baseline_end,
            )
            .scalar()
            or 0.0
        )

        effect_load = round(baseline_load - actual_load, 2) if baseline_load > actual_load else 0.0
        achievement_rate = round((effect_load / resp.committed_load) * 100, 2) if resp.committed_load > 0 else 0.0

        incentive_amount = round(effect_load * settings.DEMAND_RESPONSE_PRICE, 2)

        resp.baseline_load = baseline_load
        resp.actual_load = actual_load
        resp.effect_load = effect_load
        resp.incentive_amount = incentive_amount
        resp.status = "verified"
        resp.verified_at = datetime.utcnow()

        results.append(
            {
                "event_id": event.id,
                "event_name": event.event_name,
                "enterprise_id": resp.enterprise_id,
                "enterprise_name": enterprise.name,
                "baseline_load": baseline_load,
                "actual_load": actual_load,
                "effect_load": effect_load,
                "achievement_rate": achievement_rate,
                "incentive_amount": incentive_amount,
            }
        )

    db.commit()

    total_effect = round(sum(r["effect_load"] for r in results), 2)
    total_incentive = round(sum(r["incentive_amount"] for r in results), 2)

    return GenericResponse(
        code=200,
        message=f"响应效果核算完成，共核算{len(results)}家企业",
        data={
            "event_id": event.id,
            "event_name": event.event_name,
            "total_effect_load": total_effect,
            "total_incentive_amount": total_incentive,
            "items": results,
        },
    )
