import sys
from datetime import datetime, date, timedelta
import random

sys.path.insert(0, ".")

from app.database import SessionLocal, Base, engine
from app.models import models
from app.utils.auth import get_password_hash


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        admin_count = db.query(models.User).filter(models.User.role == "super_admin").count()
        if admin_count == 0:
            super_admin = models.User(
                username="admin",
                email="admin@smartpark.com",
                hashed_password=get_password_hash("admin123"),
                full_name="系统管理员",
                phone="13800000000",
                role="super_admin",
                is_active=True
            )
            db.add(super_admin)

            property_manager = models.User(
                username="property",
                email="property@smartpark.com",
                hashed_password=get_password_hash("123456"),
                full_name="物业管理员",
                phone="13800000001",
                role="property_manager",
                is_active=True
            )
            db.add(property_manager)

            park_manager = models.User(
                username="park",
                email="park@smartpark.com",
                hashed_password=get_password_hash("123456"),
                full_name="园区管理员",
                phone="13800000002",
                role="park_manager",
                is_active=True
            )
            db.add(park_manager)

        building_count = db.query(models.Building).count()
        buildings = []
        if building_count == 0:
            building_data = [
                {"name": "创新大厦A座", "code": "BLD-A", "address": "科技园区1号", "building_type": "办公楼",
                 "total_area": 15000.0, "floors": 15, "year_built": 2018, "park_zone": "A区"},
                {"name": "创新大厦B座", "code": "BLD-B", "address": "科技园区2号", "building_type": "办公楼",
                 "total_area": 18000.0, "floors": 18, "year_built": 2019, "park_zone": "A区"},
                {"name": "研发中心C座", "code": "BLD-C", "address": "科技园区3号", "building_type": "研发楼",
                 "total_area": 25000.0, "floors": 10, "year_built": 2020, "park_zone": "B区"},
                {"name": "生产厂房D1", "code": "BLD-D1", "address": "科技园区4号", "building_type": "厂房",
                 "total_area": 30000.0, "floors": 3, "year_built": 2017, "park_zone": "C区"},
                {"name": "综合服务楼E", "code": "BLD-E", "address": "科技园区5号", "building_type": "综合楼",
                 "total_area": 12000.0, "floors": 6, "year_built": 2021, "park_zone": "A区"},
            ]
            for bd in building_data:
                b = models.Building(**bd, status="active")
                db.add(b)
                buildings.append(b)
            db.flush()

        enterprise_count = db.query(models.Enterprise).count()
        enterprises = []
        if enterprise_count == 0:
            buildings = db.query(models.Building).all()
            enterprise_data = [
                {"name": "智慧科技有限公司", "code": "ENT-001", "industry": "信息技术",
                 "contact_person": "张总", "contact_phone": "13900001001", "contact_email": "zhang@smarttech.com",
                 "building_idx": 0, "floor": "3-5层", "occupied_area": 3000.0, "employee_count": 150},
                {"name": "绿色能源股份公司", "code": "ENT-002", "industry": "新能源",
                 "contact_person": "李总", "contact_phone": "13900001002", "contact_email": "li@greenenergy.com",
                 "building_idx": 0, "floor": "6-8层", "occupied_area": 2800.0, "employee_count": 120},
                {"name": "数据科技集团", "code": "ENT-003", "industry": "大数据",
                 "contact_person": "王总", "contact_phone": "13900001003", "contact_email": "wang@datagroup.com",
                 "building_idx": 1, "floor": "2-6层", "occupied_area": 4500.0, "employee_count": 200},
                {"name": "智能制造公司", "code": "ENT-004", "industry": "智能制造",
                 "contact_person": "赵总", "contact_phone": "13900001004", "contact_email": "zhao@smartmfg.com",
                 "building_idx": 2, "floor": "1-3层", "occupied_area": 8000.0, "employee_count": 300},
                {"name": "新材料研究院", "code": "ENT-005", "industry": "新材料",
                 "contact_person": "孙总", "contact_phone": "13900001005", "contact_email": "sun@newmat.com",
                 "building_idx": 2, "floor": "4-6层", "occupied_area": 6000.0, "employee_count": 180},
                {"name": "精密制造工厂", "code": "ENT-006", "industry": "精密制造",
                 "contact_person": "周总", "contact_phone": "13900001006", "contact_email": "zhou@precision.com",
                 "building_idx": 3, "floor": "全楼", "occupied_area": 28000.0, "employee_count": 500},
                {"name": "园区服务中心", "code": "ENT-007", "industry": "服务业",
                 "contact_person": "吴总", "contact_phone": "13900001007", "contact_email": "wu@service.com",
                 "building_idx": 4, "floor": "全楼", "occupied_area": 10000.0, "employee_count": 80},
            ]
            for ed in enterprise_data:
                e = models.Enterprise(
                    name=ed["name"], code=ed["code"], tax_id=f"TAX{ed['code']}",
                    industry=ed["industry"], contact_person=ed["contact_person"],
                    contact_phone=ed["contact_phone"], contact_email=ed["contact_email"],
                    building_id=buildings[ed["building_idx"]].id, floor=ed["floor"],
                    occupied_area=ed["occupied_area"], employee_count=ed["employee_count"],
                    status="active"
                )
                db.add(e)
                enterprises.append(e)

                ent_user = models.User(
                    username=f"user_{ed['code'].lower()}",
                    email=f"admin@{ed['code'].lower()}.com",
                    hashed_password=get_password_hash("123456"),
                    full_name=f"{ed['name']}管理员",
                    phone=ed["contact_phone"],
                    role="enterprise_user",
                    enterprise_id=len(enterprises),
                    is_active=True
                )
                db.add(ent_user)
            db.flush()

        meter_count = db.query(models.Meter).count()
        if meter_count == 0:
            enterprises = db.query(models.Enterprise).all()
            buildings = db.query(models.Building).all()
            meter_types = ["smart_meter", "gas_meter", "heat_meter", "water_meter"]
            energy_types = ["electricity", "gas", "heat", "water"]
            meter_names = {
                "electricity": "智能电表",
                "gas": "燃气表",
                "heat": "热量表",
                "water": "水表"
            }

            for b_idx, building in enumerate(buildings):
                for m_idx, (mt, et) in enumerate(zip(meter_types, energy_types)):
                    m = models.Meter(
                        code=f"M-{building.code}-{et[:3].upper()}",
                        name=f"{building.name}{meter_names[et]}",
                        meter_type=mt,
                        energy_type=et,
                        building_id=building.id,
                        location=f"{building.name}总表",
                        installation_date=date(2023, 1, 1),
                        status="active"
                    )
                    db.add(m)

            for e_idx, enterprise in enumerate(enterprises):
                for m_idx, (mt, et) in enumerate(zip(meter_types, energy_types)):
                    m = models.Meter(
                        code=f"M-{enterprise.code}-{et[:3].upper()}",
                        name=f"{enterprise.name}{meter_names[et]}",
                        meter_type=mt,
                        energy_type=et,
                        building_id=enterprise.building_id,
                        enterprise_id=enterprise.id,
                        location=f"{enterprise.floor}",
                        installation_date=date(2023, 6, 1),
                        status="active"
                    )
                    db.add(m)
            db.flush()

        energy_count = db.query(models.EnergyData).count()
        if energy_count == 0:
            meters = db.query(models.Meter).filter(models.Meter.enterprise_id.isnot(None)).all()
            base_usage = {
                "electricity": 800,
                "gas": 120,
                "heat": 500,
                "water": 60
            }

            for meter in meters:
                for day_offset in range(30):
                    current_date = date.today() - timedelta(days=day_offset)
                    for hour in range(24):
                        if 0 <= hour < 8 or hour == 23:
                            peak_type = "valley"
                        elif (8 <= hour < 11) or (18 <= hour < 22):
                            peak_type = "peak"
                        else:
                            peak_type = "flat"

                        base = base_usage.get(meter.energy_type, 100)
                        if peak_type == "valley":
                            hourly = base * 0.3 * (0.9 + random.random() * 0.2)
                        elif peak_type == "peak":
                            hourly = base * 1.3 * (0.9 + random.random() * 0.2)
                        else:
                            hourly = base * 1.0 * (0.9 + random.random() * 0.2)

                        if meter.energy_type == "electricity":
                            if peak_type == "peak":
                                price = 1.2
                            elif peak_type == "flat":
                                price = 0.8
                            else:
                                price = 0.4
                        elif meter.energy_type == "gas":
                            price = 3.5
                        elif meter.energy_type == "heat":
                            price = 35.0
                        else:
                            price = 4.5

                        ed = models.EnergyData(
                            meter_id=meter.id,
                            enterprise_id=meter.enterprise_id,
                            energy_type=meter.energy_type,
                            usage_value=round(hourly, 2),
                            data_time=datetime.combine(current_date, datetime.min.time()) + timedelta(hours=hour),
                            data_period="hour",
                            price=price,
                            peak_type=peak_type
                        )
                        db.add(ed)

        db.commit()
        print("数据库初始化完成!")
        print("默认账号: admin / admin123 (超级管理员)")
        print("         property / 123456 (物业管理员)")
        print("         park / 123456 (园区管理员)")
        print("         user_ent-001 ~ user_ent-007 / 123456 (企业用户)")

    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
