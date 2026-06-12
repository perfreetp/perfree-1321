from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Date, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(200), unique=True, index=True)
    hashed_password = Column(String(500), nullable=False)
    full_name = Column(String(100))
    phone = Column(String(20))
    role = Column(String(50), default="viewer")
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="users")
    subscriptions = relationship("AlertSubscription", back_populates="user")


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(100), unique=True, index=True)
    address = Column(String(500))
    building_type = Column(String(100))
    total_area = Column(Float, default=0.0)
    floors = Column(Integer, default=0)
    year_built = Column(Integer)
    description = Column(Text)
    park_zone = Column(String(100))
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    enterprises = relationship("Enterprise", back_populates="building")
    meters = relationship("Meter", back_populates="building")
    devices = relationship("DeviceRecord", back_populates="building")


class Enterprise(Base):
    __tablename__ = "enterprises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(100), unique=True, index=True)
    tax_id = Column(String(100))
    industry = Column(String(200))
    contact_person = Column(String(100))
    contact_phone = Column(String(20))
    contact_email = Column(String(200))
    building_id = Column(Integer, ForeignKey("buildings.id"))
    floor = Column(String(100))
    occupied_area = Column(Float, default=0.0)
    employee_count = Column(Integer, default=0)
    description = Column(Text)
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    building = relationship("Building", back_populates="enterprises")
    users = relationship("User", back_populates="enterprise")
    meters = relationship("Meter", back_populates="enterprise")
    energy_data = relationship("EnergyData", back_populates="enterprise")
    carbon_data = relationship("CarbonData", back_populates="enterprise")
    quotas = relationship("Quota", back_populates="enterprise")
    alarms = relationship("Alarm", back_populates="enterprise")
    bills = relationship("Bill", back_populates="enterprise")
    demand_responses = relationship("DemandResponse", back_populates="enterprise")
    suggestions = relationship("SavingSuggestion", back_populates="enterprise")
    monthly_reports = relationship("MonthlyReport", back_populates="enterprise")


class Meter(Base):
    __tablename__ = "meters"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    meter_type = Column(String(50), nullable=False)
    energy_type = Column(String(50), nullable=False)
    building_id = Column(Integer, ForeignKey("buildings.id"))
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    location = Column(String(200))
    installation_date = Column(Date)
    status = Column(String(50), default="active")
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    building = relationship("Building", back_populates="meters")
    enterprise = relationship("Enterprise", back_populates="meters")
    energy_data = relationship("EnergyData", back_populates="meter")


class EnergyData(Base):
    __tablename__ = "energy_data"

    id = Column(Integer, primary_key=True, index=True)
    meter_id = Column(Integer, ForeignKey("meters.id"), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    energy_type = Column(String(50), nullable=False)
    usage_value = Column(Float, nullable=False)
    data_time = Column(DateTime(timezone=True), nullable=False, index=True)
    data_period = Column(String(50), default="hour")
    price = Column(Float, default=0.0)
    peak_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meter = relationship("Meter", back_populates="energy_data")
    enterprise = relationship("Enterprise", back_populates="energy_data")


class CarbonData(Base):
    __tablename__ = "carbon_data"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    energy_type = Column(String(50), nullable=False)
    carbon_emission = Column(Float, nullable=False)
    data_date = Column(Date, nullable=False, index=True)
    period = Column(String(50), default="day")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="carbon_data")


class Quota(Base):
    __tablename__ = "quotas"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    energy_type = Column(String(50), nullable=False)
    quota_value = Column(Float, nullable=False)
    quota_period = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    warning_threshold = Column(Float, default=80.0)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="quotas")


class CarbonBudget(Base):
    __tablename__ = "carbon_budgets"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    budget_value = Column(Float, nullable=False)
    period = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    allocated_by = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    alarm_type = Column(String(100), nullable=False)
    energy_type = Column(String(50))
    level = Column(String(50), default="warning")
    title = Column(String(500), nullable=False)
    content = Column(Text)
    value = Column(Float)
    threshold = Column(Float)
    status = Column(String(50), default="pending")
    alarm_time = Column(DateTime(timezone=True), nullable=False)
    processed_time = Column(DateTime(timezone=True))
    processed_by = Column(String(100))
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="alarms")


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    alarm_type = Column(String(100), nullable=False)
    notify_email = Column(Boolean, default=True)
    notify_sms = Column(Boolean, default=False)
    notify_wechat = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="subscriptions")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    bill_month = Column(String(20), nullable=False)
    energy_type = Column(String(50), nullable=False)
    usage = Column(Float, nullable=False)
    peak_usage = Column(Float, default=0.0)
    flat_usage = Column(Float, default=0.0)
    valley_usage = Column(Float, default=0.0)
    amount = Column(Float, nullable=False)
    peak_amount = Column(Float, default=0.0)
    flat_amount = Column(Float, default=0.0)
    valley_amount = Column(Float, default=0.0)
    status = Column(String(50), default="unpaid")
    due_date = Column(Date)
    paid_date = Column(Date)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="bills")


class DemandResponseEvent(Base):
    __tablename__ = "demand_response_events"

    id = Column(Integer, primary_key=True, index=True)
    event_code = Column(String(100), unique=True, index=True)
    event_name = Column(String(200), nullable=False)
    response_type = Column(String(50), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    target_load = Column(Float, nullable=False)
    status = Column(String(50), default="open")
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    responses = relationship("DemandResponse", back_populates="event")


class DemandResponse(Base):
    __tablename__ = "demand_responses"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("demand_response_events.id"), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    signed_up = Column(Boolean, default=False)
    committed_load = Column(Float, default=0.0)
    actual_load = Column(Float, default=0.0)
    baseline_load = Column(Float, default=0.0)
    effect_load = Column(Float, default=0.0)
    incentive_amount = Column(Float, default=0.0)
    status = Column(String(50), default="pending")
    signed_at = Column(DateTime(timezone=True))
    verified_at = Column(DateTime(timezone=True))
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("DemandResponseEvent", back_populates="responses")
    enterprise = relationship("Enterprise", back_populates="demand_responses")


class DeviceRecord(Base):
    __tablename__ = "device_records"

    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"))
    device_name = Column(String(200), nullable=False)
    device_code = Column(String(100))
    action_type = Column(String(50), nullable=False)
    operator = Column(String(100))
    action_time = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text)
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    building = relationship("Building", back_populates="devices")


class SavingSuggestion(Base):
    __tablename__ = "saving_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    suggestion_type = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    potential_saving = Column(Float, default=0.0)
    saving_unit = Column(String(50))
    priority = Column(String(50), default="medium")
    status = Column(String(50), default="new")
    generated_at = Column(DateTime(timezone=True), nullable=False)
    handled_by = Column(String(100))
    handled_at = Column(DateTime(timezone=True))
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="suggestions")


class LoadForecast(Base):
    __tablename__ = "load_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    energy_type = Column(String(50), nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    forecast_value = Column(Float, nullable=False)
    actual_value = Column(Float)
    forecast_period = Column(String(50), default="hour")
    model_type = Column(String(50), default="arima")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    report_month = Column(String(20), nullable=False)
    energy_total = Column(Float, default=0.0)
    energy_electricity = Column(Float, default=0.0)
    energy_gas = Column(Float, default=0.0)
    energy_heat = Column(Float, default=0.0)
    energy_water = Column(Float, default=0.0)
    carbon_total = Column(Float, default=0.0)
    cost_total = Column(Float, default=0.0)
    quota_usage_rate = Column(Float, default=0.0)
    ranking = Column(Integer)
    analysis = Column(Text)
    suggestions = Column(Text)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    enterprise = relationship("Enterprise", back_populates="monthly_reports")


class AbnormalUsage(Base):
    __tablename__ = "abnormal_usages"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    energy_type = Column(String(50), nullable=False)
    abnormal_type = Column(String(100), nullable=False)
    detected_time = Column(DateTime(timezone=True), nullable=False)
    value = Column(Float, nullable=False)
    expected_value = Column(Float)
    deviation_rate = Column(Float)
    description = Column(Text)
    status = Column(String(50), default="detected")
    handled_by = Column(String(100))
    handled_at = Column(DateTime(timezone=True))
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
