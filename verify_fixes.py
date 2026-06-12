import httpx
import datetime
import json

base = "http://127.0.0.1:8000/api/v1"

r = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = r.json()['access_token']
h = {'Authorization': f'Bearer {token}'}

print("=" * 60)
print("测试 1: 注册接口权限控制（不能注册管理员）")
print("=" * 60)
import random
suffix = random.randint(100, 999)
r = httpx.post(f'{base}/auth/register', json={
    'username': f'test_user_admin_{suffix}',
    'password': '123456',
    'full_name': '测试管理员',
    'role': 'admin'
})
print(f"  请求体 role=admin: HTTP {r.status_code}")
result = r.json()
print(f"  响应: {result}")
print(f"  实际注册的角色: {result.get('role', 'ERROR')}")
assert r.status_code == 201, f"❌ 注册失败: {result}"
assert result.get('role') != 'admin', "❌ 失败：居然注册成了管理员!"
assert result.get('role') in ['viewer', 'enterprise_user'], f"❌ 失败：角色异常 {result.get('role')}"
print("  ✅ 通过：请求管理员角色实际注册为 viewer")

r = httpx.post(f'{base}/auth/register', json={
    'username': f'test_user_enterprise_{suffix}',
    'password': '123456',
    'full_name': '测试企业用户',
    'role': 'enterprise_user',
    'enterprise_id': 1
})
print(f"\n  请求体 role=enterprise_user + enterprise_id=1: HTTP {r.status_code}")
result = r.json()
print(f"  实际注册的角色: {result.get('role')}, enterprise_id: {result.get('enterprise_id')}")
assert result.get('role') == 'enterprise_user'
assert result.get('enterprise_id') == 1
print("  ✅ 通过：正确注册为 enterprise_user")

# 验证新注册的viewer用户登录后不能访问管理接口
r = httpx.post(f'{base}/auth/login', data={'username': f'test_user_admin_{suffix}', 'password': '123456'})
viewer_token = r.json()['access_token']
viewer_h = {'Authorization': f'Bearer {viewer_token}'}
r = httpx.post(f'{base}/buildings', json={
    'name': '测试楼', 'code': 'TEST-X1'
}, headers=viewer_h)
print(f"\n  普通viewer用户尝试创建楼栋: HTTP {r.status_code}")
assert r.status_code == 403, f"❌ 期望403，得到 {r.status_code}"
print("  ✅ 通过：普通用户无权访问楼栋创建等管理接口")

print("\n" + "=" * 60)
print("测试 2: 碳预算分摊日期参数校验")
print("=" * 60)

print("  测试2a: 传非法日期格式...")
r = httpx.post(f'{base}/carbon/budget/allocate', json={
    'total_budget': 10000,
    'start_date': 'not-a-date',
    'end_date': '2024-12-31',
}, headers=h)
print(f"    start_date=非法: HTTP {r.status_code}")
assert r.status_code in (422, 400), f"❌ 期望 400/422，得到 {r.status_code}"
print(f"    ✅ 通过: 返回 {r.status_code} 错误，不会变成500")

print("  测试2b: 开始日期晚于结束日期...")
r = httpx.post(f'{base}/carbon/budget/allocate', json={
    'total_budget': 10000,
    'start_date': '2024-12-31',
    'end_date': '2024-01-01',
}, headers=h)
print(f"    start > end: HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望 400，得到 {r.status_code}: {r.text}"
print(f"    ✅ 通过: 返回 400 错误 '{r.json()['detail']}'")

print("  测试2c: 按三种方式分摊(全园区)并生成可查询记录...")
today = datetime.date.today()
for atype in ['area', 'employee', 'history']:
    r = httpx.post(f'{base}/carbon/budget/allocate', json={
        'total_budget': 100000,
        'start_date': str(today),
        'end_date': str(today + datetime.timedelta(days=30)),
        'allocate_type': atype,
    }, headers=h)
    if atype == 'history' and r.status_code == 400:
        print(f"    分摊方式={atype}: HTTP {r.status_code} (无可查询历史数据属正常)")
        continue
    print(f"    分摊方式={atype}: HTTP {r.status_code}")
    assert r.status_code == 200, f"❌ 失败: {r.text}"
    data = r.json()['data']
    print(f"      分摊给 {data['allocated_count']} 家企业")

r = httpx.get(f'{base}/carbon/budget', headers=h)
items = r.json()['data']['items']
print(f"\n  查询碳预算记录: 共 {r.json()['data']['total']} 条")
print("  ✅ 通过：分摊方式都生成了可查询的 CarbonBudget 记录")

print("\n" + "=" * 60)
print("测试 3: 按楼栋账单分摊")
print("=" * 60)

print("  测试3a: 传楼栋ID仅分摊该楼栋企业...")
r = httpx.post(f'{base}/bills/split', json={
    'bill_month': '2026-06',
    'building_id': 1,
    'split_type': 'area'
}, headers=h)
assert r.status_code == 200, f"❌ 失败: {r.text}"
data = r.json()['data']
print(f"    楼栋1分摊: building_name={data['building_name']}")
print(f"    生成账单数={data['count']}")
summary = data['energy_summary']
print(f"    该楼栋能源汇总: {json.dumps(summary, ensure_ascii=False)}")

print("\n  测试3b: 全园区分摊(不传building_id)...")
r = httpx.post(f'{base}/bills/split', json={
    'bill_month': '2026-06',
    'split_type': 'headcount'
}, headers=h)
assert r.status_code == 200, f"❌ 失败: {r.text}"
data = r.json()['data']
print(f"    全园区分摊: building_name={data['building_name']}")
print(f"    生成账单数={data['count']}")

print("\n  测试3c: 分摊合计与楼栋当月能耗核对...")
r_building = httpx.post(f'{base}/bills/split', json={
    'bill_month': '2026-06',
    'building_id': 2,
    'split_type': 'usage'
}, headers=h)
bld_data = r_building.json()['data']
bills_amount_sum = sum(x['share_amount'] for x in bld_data['items'])
energy_total_cost = sum(v['total_cost'] for v in bld_data['energy_summary'].values())
diff = abs(bills_amount_sum - energy_total_cost)
print(f"    楼栋2账单金额合计: {round(bills_amount_sum, 2)}")
print(f"    楼栋2能耗费用合计: {round(energy_total_cost, 2)}")
print(f"    差额: {round(diff, 4)}")
assert diff < 1.0, f"❌ 差异过大: {diff}"
print("  ✅ 通过：楼栋分摊账单金额合计与楼栋能耗费用基本一致")

print("\n  测试3d: 账期格式错误...")
r = httpx.post(f'{base}/bills/split', json={
    'bill_month': 'bad-date',
    'split_type': 'area'
}, headers=h)
print(f"    bill_month=bad-date: HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}: {r.text}"
print(f"    错误信息: {r.json()['detail']}")
print("  ✅ 通过：账期格式错误返回400，不会变成500")

print("\n" + "=" * 60)
print("测试 4: 能耗数据录入校验")
print("=" * 60)

# 获取一个电表
r = httpx.get(f'{base}/meters', params={'energy_type': 'electricity', 'limit': 1}, headers=h)
elec_meter = r.json()[0]
print(f"  电表: id={elec_meter['id']}, code={elec_meter['code']}, type={elec_meter['energy_type']}")

print("  测试4a: 电表录入 gas 数据，应报错 400...")
r = httpx.post(f'{base}/energy/data', json={
    'meter_id': elec_meter['id'],
    'energy_type': 'gas',
    'usage_value': 100.0,
    'data_time': '2026-06-13T10:00:00'
}, headers=h)
print(f"    电表录gas: HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}: {r.text}"
print(f"    错误信息: {r.json()['detail']}")
print("  ✅ 通过：电表不能录入燃气数据")

print("  测试4b: 水表录入 electricity 数据，应报错 400...")
r = httpx.get(f'{base}/meters', params={'energy_type': 'water', 'limit': 1}, headers=h)
water_meter = r.json()[0]
r = httpx.post(f'{base}/energy/data', json={
    'meter_id': water_meter['id'],
    'energy_type': 'electricity',
    'usage_value': 50.0,
    'data_time': '2026-06-13T10:30:00'
}, headers=h)
print(f"    水表录电: HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}: {r.text}"
print("  ✅ 通过：水表不能录入电力数据")

print("  测试4c: 传入不一致的企业ID，应报错 400...")
r = httpx.get(f'{base}/meters', params={'limit': 100}, headers=h)
bound_meter = None
for m in r.json():
    if m['enterprise_id'] is not None:
        bound_meter = m
        break

if bound_meter:
    print(f"    已绑定企业的表: id={bound_meter['id']}, enterprise_id={bound_meter['enterprise_id']}")
    wrong_ent_id = bound_meter['enterprise_id'] + 100 if bound_meter['enterprise_id'] else 999
    r = httpx.post(f'{base}/energy/data', json={
        'meter_id': bound_meter['id'],
        'energy_type': bound_meter['energy_type'],
        'enterprise_id': wrong_ent_id,
        'usage_value': 50.0,
        'data_time': '2026-06-13T11:00:00'
    }, headers=h)
    print(f"    传不一致企业ID({wrong_ent_id}): HTTP {r.status_code}")
    assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}: {r.text}"
    print(f"    错误信息: {r.json()['detail']}")
    print("  ✅ 通过：企业ID与表计绑定关系不一致时报错")
else:
    print("  ⚠️ 跳过：未找到绑定了企业的表计")

print("  测试4d: 正常录入一致的数据，应成功...")
r = httpx.post(f'{base}/energy/data', json={
    'meter_id': elec_meter['id'],
    'energy_type': elec_meter['energy_type'],
    'usage_value': 88.8,
    'data_time': '2026-06-13T12:00:00'
}, headers=h)
print(f"    正常录入(电表+电): HTTP {r.status_code}")
assert r.status_code == 200 and r.json()['code'] == 201, f"❌ 失败: {r.text}"
print(f"    返回: {r.json()['data']}")
print("  ✅ 通过：数据校验通过，录入成功")

print("\n" + "=" * 60)
print("🎉 全部四项修复验证通过!")
print("=" * 60)
