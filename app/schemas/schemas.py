from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date, time
from enum import Enum


class EnergyType(str, Enum):
    ELECTRICITY = "electricity"
    GAS = "gas"
    HEAT = "heat"
    WATER = "water"


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PARK_MANAGER = "park_manager"
    PROPERTY_MANAGER = "property_manager"
    ENTERPRISE_USER = "enterprise_user"
    VIEWER = "viewer"


class UserBase(BaseModel):
    username: str = Field(..., max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "viewer"
    enterprise_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    enterprise_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    username: Optional[str] = None


class BuildingBase(BaseModel):
    name: str = Field(..., max_length=200)
    code: Optional[str] = None
    address: Optional[str] = None
    building_type: Optional[str] = None
    total_area: Optional[float] = 0.0
    floors: Optional[int] = 0
    year_built: Optional[int] = None
    description: Optional[str] = None
    park_zone: Optional[str] = None
    status: Optional[str] = "active"


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    building_type: Optional[str] = None
    total_area: Optional[float] = None
    floors: Optional[int] = None
    year_built: Optional[int] = None
    description: Optional[str] = None
    park_zone: Optional[str] = None
    status: Optional[str] = None


class BuildingResponse(BuildingBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnterpriseBase(BaseModel):
    name: str = Field(..., max_length=200)
    code: Optional[str] = None
    tax_id: Optional[str] = None
    industry: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    building_id: Optional[int] = None
    floor: Optional[str] = None
    occupied_area: Optional[float] = 0.0
    employee_count: Optional[int] = 0
    description: Optional[str] = None
    status: Optional[str] = "active"


class EnterpriseCreate(EnterpriseBase):
    pass


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    industry: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    building_id: Optional[int] = None
    floor: Optional[str] = None
    occupied_area: Optional[float] = None
    employee_count: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


class EnterpriseResponse(EnterpriseBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MeterBase(BaseModel):
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    meter_type: str = Field(..., max_length=50)
    energy_type: str = Field(..., max_length=50)
    building_id: Optional[int] = None
    enterprise_id: Optional[int] = None
    location: Optional[str] = None
    installation_date: Optional[date] = None
    status: Optional[str] = "active"
    description: Optional[str] = None


class MeterCreate(MeterBase):
    pass


class MeterUpdate(BaseModel):
    name: Optional[str] = None
    meter_type: Optional[str] = None
    energy_type: Optional[str] = None
    building_id: Optional[int] = None
    enterprise_id: Optional[int] = None
    location: Optional[str] = None
    installation_date: Optional[date] = None
    status: Optional[str] = None
    description: Optional[str] = None


class MeterResponse(MeterBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnergyDataBase(BaseModel):
    meter_id: int
    enterprise_id: Optional[int] = None
    energy_type: str
    usage_value: float
    data_time: datetime
    data_period: Optional[str] = "hour"
    price: Optional[float] = 0.0
    peak_type: Optional[str] = None


class EnergyDataCreate(EnergyDataBase):
    pass


class EnergyDataResponse(EnergyDataBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnergySummaryQuery(BaseModel):
    enterprise_id: Optional[int] = None
    building_id: Optional[int] = None
    energy_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    group_by: Optional[str] = "day"
    park_zone: Optional[str] = None


class EnergySummaryItem(BaseModel):
    time_label: str
    energy_type: Optional[str] = None
    usage_value: float
    cost: Optional[float] = None
    peak_usage: Optional[float] = None
    flat_usage: Optional[float] = None
    valley_usage: Optional[float] = None


class RealtimeLoadQuery(BaseModel):
    enterprise_id: Optional[int] = None
    building_id: Optional[int] = None
    energy_type: Optional[str] = "electricity"


class RealtimeLoadItem(BaseModel):
    time_point: datetime
    load_value: float
    energy_type: str


class CarbonDataBase(BaseModel):
    enterprise_id: Optional[int] = None
    energy_type: str
    carbon_emission: float
    data_date: date
    period: Optional[str] = "day"


class CarbonDataCreate(CarbonDataBase):
    pass


class CarbonDataResponse(CarbonDataBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CarbonCalculateQuery(BaseModel):
    enterprise_id: Optional[int] = None
    energy_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CarbonCalculateResult(BaseModel):
    energy_type: str
    energy_usage: float
    carbon_factor: float
    carbon_emission: float


class CarbonBudgetBase(BaseModel):
    enterprise_id: int
    budget_value: float
    period: str
    start_date: date
    end_date: date
    allocated_by: Optional[str] = None
    description: Optional[str] = None


class CarbonBudgetCreate(CarbonBudgetBase):
    pass


class CarbonBudgetUpdate(BaseModel):
    budget_value: Optional[float] = None
    period: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    allocated_by: Optional[str] = None
    description: Optional[str] = None


class CarbonBudgetResponse(CarbonBudgetBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QuotaBase(BaseModel):
    enterprise_id: int
    energy_type: str
    quota_value: float
    quota_period: str
    start_date: date
    end_date: date
    warning_threshold: Optional[float] = 80.0
    description: Optional[str] = None


class QuotaCreate(QuotaBase):
    pass


class QuotaUpdate(BaseModel):
    quota_value: Optional[float] = None
    quota_period: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    warning_threshold: Optional[float] = None
    description: Optional[str] = None


class QuotaResponse(QuotaBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QuotaUsage(BaseModel):
    quota_id: int
    enterprise_id: int
    energy_type: str
    quota_value: float
    used_value: float
    usage_rate: float
    start_date: date
    end_date: date


class PeakValleyPriceQuery(BaseModel):
    enterprise_id: int
    energy_type: Optional[str] = "electricity"
    start_date: date
    end_date: date


class PeakValleyPriceResult(BaseModel):
    peak_usage: float
    peak_price: float
    peak_amount: float
    flat_usage: float
    flat_price: float
    flat_amount: float
    valley_usage: float
    valley_price: float
    valley_amount: float
    total_usage: float
    total_amount: float


class AbnormalUsageBase(BaseModel):
    enterprise_id: Optional[int] = None
    energy_type: str
    abnormal_type: str
    detected_time: datetime
    value: float
    expected_value: Optional[float] = None
    deviation_rate: Optional[float] = None
    description: Optional[str] = None
    status: Optional[str] = "detected"
    handled_by: Optional[str] = None
    handled_at: Optional[datetime] = None
    remark: Optional[str] = None


class AbnormalUsageCreate(AbnormalUsageBase):
    pass


class AbnormalUsageUpdate(BaseModel):
    status: Optional[str] = None
    handled_by: Optional[str] = None
    handled_at: Optional[datetime] = None
    remark: Optional[str] = None


class AbnormalUsageResponse(AbnormalUsageBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AbnormalDetectQuery(BaseModel):
    enterprise_id: Optional[int] = None
    energy_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    abnormal_type: Optional[str] = None


class LoadForecastQuery(BaseModel):
    model_config = {"protected_namespaces": ()}
    enterprise_id: int
    energy_type: Optional[str] = "electricity"
    forecast_hours: Optional[int] = 24
    model_type: Optional[str] = "arima"


class LoadForecastItem(BaseModel):
    forecast_time: datetime
    forecast_value: float
    energy_type: str


class LoadForecastBase(BaseModel):
    model_config = {"protected_namespaces": ()}
    enterprise_id: Optional[int] = None
    energy_type: str
    forecast_time: datetime
    forecast_value: float
    actual_value: Optional[float] = None
    forecast_period: Optional[str] = "hour"
    model_type: Optional[str] = "arima"


class LoadForecastResponse(LoadForecastBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlarmBase(BaseModel):
    enterprise_id: Optional[int] = None
    alarm_type: str
    energy_type: Optional[str] = None
    level: Optional[str] = "warning"
    title: str
    content: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    status: Optional[str] = "pending"
    alarm_time: datetime
    processed_time: Optional[datetime] = None
    processed_by: Optional[str] = None
    remark: Optional[str] = None


class AlarmCreate(AlarmBase):
    pass


class AlarmUpdate(BaseModel):
    status: Optional[str] = None
    processed_time: Optional[datetime] = None
    processed_by: Optional[str] = None
    remark: Optional[str] = None


class AlarmResponse(AlarmBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertSubscriptionBase(BaseModel):
    user_id: int
    alarm_type: str
    notify_email: Optional[bool] = True
    notify_sms: Optional[bool] = False
    notify_wechat: Optional[bool] = False
    enabled: Optional[bool] = True


class AlertSubscriptionCreate(AlertSubscriptionBase):
    pass


class AlertSubscriptionUpdate(BaseModel):
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_wechat: Optional[bool] = None
    enabled: Optional[bool] = None


class AlertSubscriptionResponse(AlertSubscriptionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BillBase(BaseModel):
    enterprise_id: int
    bill_month: str
    energy_type: str
    usage: float
    peak_usage: Optional[float] = 0.0
    flat_usage: Optional[float] = 0.0
    valley_usage: Optional[float] = 0.0
    amount: float
    peak_amount: Optional[float] = 0.0
    flat_amount: Optional[float] = 0.0
    valley_amount: Optional[float] = 0.0
    status: Optional[str] = "unpaid"
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    description: Optional[str] = None


class BillCreate(BillBase):
    pass


class BillUpdate(BaseModel):
    status: Optional[str] = None
    paid_date: Optional[date] = None
    description: Optional[str] = None


class BillResponse(BillBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BillSplitQuery(BaseModel):
    bill_month: str
    building_id: Optional[int] = None
    split_type: Optional[str] = "area"


class BillSplitItem(BaseModel):
    enterprise_id: int
    enterprise_name: str
    total_usage: float
    share_ratio: float
    share_amount: float
    energy_type: str


class DemandResponseEventBase(BaseModel):
    event_code: Optional[str] = None
    event_name: str
    response_type: str
    start_time: datetime
    end_time: datetime
    target_load: float
    status: Optional[str] = "open"
    description: Optional[str] = None


class DemandResponseEventCreate(DemandResponseEventBase):
    pass


class DemandResponseEventUpdate(BaseModel):
    event_name: Optional[str] = None
    response_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    target_load: Optional[float] = None
    status: Optional[str] = None
    description: Optional[str] = None


class DemandResponseEventResponse(DemandResponseEventBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DemandResponseBase(BaseModel):
    event_id: int
    enterprise_id: int
    signed_up: Optional[bool] = False
    committed_load: Optional[float] = 0.0
    actual_load: Optional[float] = 0.0
    baseline_load: Optional[float] = 0.0
    effect_load: Optional[float] = 0.0
    incentive_amount: Optional[float] = 0.0
    status: Optional[str] = "pending"
    signed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    remark: Optional[str] = None


class DemandResponseCreate(BaseModel):
    event_id: int
    enterprise_id: int
    committed_load: float


class DemandResponseUpdate(BaseModel):
    actual_load: Optional[float] = None
    baseline_load: Optional[float] = None
    effect_load: Optional[float] = None
    incentive_amount: Optional[float] = None
    status: Optional[str] = None
    verified_at: Optional[datetime] = None
    remark: Optional[str] = None


class DemandResponseResponse(DemandResponseBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DemandResponseEffect(BaseModel):
    event_id: int
    event_name: str
    enterprise_id: int
    enterprise_name: str
    baseline_load: float
    actual_load: float
    effect_load: float
    achievement_rate: float
    incentive_amount: float


class DeviceRecordBase(BaseModel):
    building_id: Optional[int] = None
    device_name: str
    device_code: Optional[str] = None
    action_type: str
    operator: Optional[str] = None
    action_time: datetime
    reason: Optional[str] = None
    remark: Optional[str] = None


class DeviceRecordCreate(DeviceRecordBase):
    pass


class DeviceRecordResponse(DeviceRecordBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SavingSuggestionBase(BaseModel):
    enterprise_id: Optional[int] = None
    suggestion_type: str
    title: str
    content: str
    potential_saving: Optional[float] = 0.0
    saving_unit: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "new"
    generated_at: datetime
    handled_by: Optional[str] = None
    handled_at: Optional[datetime] = None
    remark: Optional[str] = None


class SavingSuggestionCreate(SavingSuggestionBase):
    pass


class SavingSuggestionUpdate(BaseModel):
    status: Optional[str] = None
    handled_by: Optional[str] = None
    handled_at: Optional[datetime] = None
    remark: Optional[str] = None


class SavingSuggestionResponse(SavingSuggestionBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SavingSuggestionGenerate(BaseModel):
    enterprise_id: Optional[int] = None
    suggestion_type: Optional[str] = None


class MonthlyReportBase(BaseModel):
    enterprise_id: int
    report_month: str
    energy_total: Optional[float] = 0.0
    energy_electricity: Optional[float] = 0.0
    energy_gas: Optional[float] = 0.0
    energy_heat: Optional[float] = 0.0
    energy_water: Optional[float] = 0.0
    carbon_total: Optional[float] = 0.0
    cost_total: Optional[float] = 0.0
    quota_usage_rate: Optional[float] = 0.0
    ranking: Optional[int] = None
    analysis: Optional[str] = None
    suggestions: Optional[str] = None


class MonthlyReportCreate(MonthlyReportBase):
    pass


class MonthlyReportResponse(MonthlyReportBase):
    id: int
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MonthlyReportGenerate(BaseModel):
    report_month: str
    enterprise_id: Optional[int] = None


class EnterpriseRankingQuery(BaseModel):
    report_month: Optional[str] = None
    sort_by: Optional[str] = "energy_total"
    order: Optional[str] = "asc"
    limit: Optional[int] = 20


class EnterpriseRankingItem(BaseModel):
    rank: int
    enterprise_id: int
    enterprise_name: str
    energy_total: float
    energy_electricity: float
    carbon_total: float
    cost_total: float
    quota_usage_rate: float
    per_capita_energy: Optional[float] = None
    per_area_energy: Optional[float] = None


class GenericResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None
