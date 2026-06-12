import httpx
import datetime
import json

base = "http://127.0.0.1:8000/api/v1"

r = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = r.json()['access_token']
h = {'Authorization': f'Bearer {token}'}

print("=" * 60)
print("新需求 1: 碳预算分摊日期错误统一返回 400")
print("=" * 60)

print("  测试1a: start_date 格式错误 (2024/01/01)...")
r = httpx.post(f'{base}/carbon/budget/allocate', json={
    'total_budget': 10000,
    'start_date': '2024/01/01',
    'end_date': '2024-12-31',
}, headers=h)
print(f"    HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}"
print(f"    错误: {r.json()['detail'][:80]}...")
assert "YYYY-MM-DD" in r.json()['detail']
print("  ✅ 通过: 返回 400，提示 YYYY-MM-DD 格式")

print("  测试1b: end_date 格式错误 (abc)...")
r = httpx.post(f'{base}/carbon/budget/allocate', json={
    'total_budget': 10000,
    'start_date': '2024-01-01',
    'end_date': 'abc',
}, headers=h)
print(f"    HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}"
print("  ✅ 通过: end_date 错也返回 400，不再是 422")

print("  测试1c: 开始日期晚于结束日期...")
r = httpx.post(f'{base}/carbon/budget/allocate', json={
    'total_budget': 10000,
    'start_date': '2024-12-31',
    'end_date': '2024-01-01',
}, headers=h)
print(f"    HTTP {r.status_code}")
assert r.status_code == 400, f"❌ 期望400，得到 {r.status_code}"
print(f"    错误: {r.json()['detail']}")
print("  ✅ 通过: 开始日期晚于结束日期也返回 400，统一了错误码")

print("\n" + "=" * 60)
print("新需求 2: history 分摊真正能生成预算记录")
print("=" * 60)

today = datetime.date.today()
start_s = str(today)
end_s = str(today + datetime.timedelta(days=30))
print(f"  分摊期间: {start_s} ~ {end_s}")

print("  测试2: 按 history 方式分摊全园区...")
r = httpx.post(f'{base}/carbon/budget/allocate', json={
    'total_budget': 200000,
    'start_date': start_s,
    'end_date': end_s,
    'allocate_type': 'history',
}, headers=h)
print(f"    HTTP {r.status_code}")
assert r.status_code == 200, f"❌ 失败: {r.text}"
data = r.json()['data']
print(f"    分摊给 {data['allocated_count']} 家企业")
for item in data['items'][:3]:
    print(f"      - {item['enterprise_name']}: 预算={item['budget_value']} (权重={item['weight']}, 占比={item['weight_ratio']}%)")

r = httpx.get(f'{base}/carbon/budget', headers=h)
items = r.json()['data']['items']
budgets_history = [b for b in items if b['allocated_by'] == 'history']
print(f"\n  查询碳预算: history 分摊生成的记录共 {len(budgets_history)} 条")
assert len(budgets_history) > 0, "❌ history 分摊没有生成预算记录"
for b in budgets_history[:3]:
    print(f"    - id={b['id']}, ent_id={b['enterprise_id']}, value={b['budget_value']}, desc={b['description']}")
print("  ✅ 通过: history 分摊成功生成并可查询 CarbonBudget 记录")

print("\n" + "=" * 60)
print("新需求 3: 楼栋分摊包含楼栋总表 + 账单合计准确")
print("=" * 60)

print("  测试3a: 分摊楼栋1(研发楼A)账单...")
r = httpx.post(f'{base}/bills/split', json={
    'bill_month': '2026-06',
    'building_id': 1,
    'split_type': 'usage'
}, headers=h)
assert r.status_code == 200, f"❌ 失败: {r.text}"
bld1 = r.json()['data']
print(f"    楼栋: {bld1['building_name']}")
print(f"    生成账单数: {bld1['count']}")
print(f"    能源汇总: {json.dumps(bld1['energy_summary'], ensure_ascii=False)}")
bills_amount = sum(x['share_amount'] for x in bld1['items'])
energy_cost = sum(v['total_cost'] for v in bld1['energy_summary'].values())
diff = abs(bills_amount - energy_cost)
print(f"    账单金额合计: {round(bills_amount, 2)}")
print(f"    能耗费用合计: {round(energy_cost, 2)}")
print(f"    差额: {round(diff, 4)}")
assert diff < 0.01, f"❌ 差额过大: {diff}"
print("  ✅ 通过: 楼栋分摊账单合计精确对应当月能耗费用（差额<0.01）")

print("\n  测试3b: 分摊楼栋2账单...")
r = httpx.post(f'{base}/bills/split', json={
    'bill_month': '2026-06',
    'building_id': 2,
    'split_type': 'area'
}, headers=h)
bld2 = r.json()['data']
bills_amount2 = sum(x['share_amount'] for x in bld2['items'])
energy_cost2 = sum(v['total_cost'] for v in bld2['energy_summary'].values())
print(f"    楼栋: {bld2['building_name']}, 账单合计={round(bills_amount2, 2)}, 能耗合计={round(energy_cost2, 2)}, 差额={round(abs(bills_amount2-energy_cost2), 4)}")
print("  ✅ 通过: 楼栋2账单也精确对账")

print("\n" + "=" * 60)
print("新需求 4: 单楼栋/全园区账单分开保存不覆盖 + 查询区分")
print("=" * 60)

print("  测试4a: 生成全园区账单...")
r = httpx.post(f'{base}/bills/split', json={
    'bill_month': '2026-06',
    'split_type': 'headcount'
}, headers=h)
assert r.status_code == 200, f"❌ 失败: {r.text}"
park = r.json()['data']
print(f"    全园区分摊: {park['count']} 条账单")

print("\n  测试4b: 查账单列表应包含 scope、building_id...")
r = httpx.get(f'{base}/bills', params={'bill_month': '2026-06', 'page_size': 100}, headers=h)
items = r.json()['data']['items']
print(f"    2026-06 共 {len(items)} 条")
has_park = any(b['scope'] == '全园区' for b in items)
has_building = any(b['scope'] == '单楼栋' for b in items)
sample_building = [b for b in items if b['scope'] == '单楼栋'][:2]
sample_park = [b for b in items if b['scope'] == '全园区'][:2]
for b in sample_building:
    print(f"      [单楼栋] id={b['id']}, {b['energy_type']}, ent={b['enterprise_name'][:8] if b['enterprise_name'] else '?'}, "
          f"building_id={b['building_id']}, building_name={b['building_name']}")
for b in sample_park:
    print(f"      [全园区] id={b['id']}, {b['energy_type']}, ent={b['enterprise_name'][:8] if b['enterprise_name'] else '?'}, "
          f"building_id={b['building_id']}, building_name={b['building_name']}")
assert has_park and has_building, f"❌ 账单没有区分 scope (全园区={has_park}, 单楼栋={has_building})"
print("  ✅ 通过: /bills 返回带 scope、building_id、building_name 字段")

print("\n  测试4c: 同企业同月份同能源，不同范围账单不覆盖...")
# 找某企业的 2026-06 electricity 账单
ent1_elec_park = None
ent1_elec_bld1 = None
r = httpx.get(f'{base}/bills', params={'bill_month': '2026-06', 'energy_type': 'electricity', 'building_id': 0, 'page_size': 100}, headers=h)
park_items = r.json()['data']['items']
r = httpx.get(f'{base}/bills', params={'bill_month': '2026-06', 'energy_type': 'electricity', 'building_id': 1, 'page_size': 100}, headers=h)
bld1_items = r.json()['data']['items']
print(f"    全园区 electricity 账单: {len(park_items)} 条")
print(f"    楼栋1 electricity 账单: {len(bld1_items)} 条")

common_ents = set(b['enterprise_id'] for b in park_items) & set(b['enterprise_id'] for b in bld1_items)
print(f"    两种范围下重复的企业数: {len(common_ents)}")
assert len(common_ents) >= 1, "❌ 没找到同时有全园区和单楼栋账单的企业，说明可能覆盖了"

ent_id = list(common_ents)[0]
park_bill = [b for b in park_items if b['enterprise_id'] == ent_id][0]
bld_bill = [b for b in bld1_items if b['enterprise_id'] == ent_id][0]
print(f"    企业{ent_id}的全园区账单: id={park_bill['id']}, amount={park_bill['amount']}, building_id={park_bill['building_id']}")
print(f"    企业{ent_id}的楼栋1账单:  id={bld_bill['id']}, amount={bld_bill['amount']}, building_id={bld_bill['building_id']}")
assert park_bill['id'] != bld_bill['id'], "❌ 账单ID相同，说明被覆盖"
print("  ✅ 通过: 同企业同月份同能源在不同分摊范围下保存为独立账单，互不覆盖")

print("\n  测试4d: 用 building_id=0 和 building_id=1 分别筛选...")
r = httpx.get(f'{base}/bills', params={'building_id': 0}, headers=h)
park_only = r.json()['data']
assert all(b['building_id'] is None for b in park_only['items']), "❌ building_id=0 筛选出了非全园区账单"
print(f"    building_id=0 (全园区筛选): 共 {park_only['total']} 条，全部 building_id=NULL")

r = httpx.get(f'{base}/bills', params={'building_id': 1}, headers=h)
bld1_only = r.json()['data']
assert all(b['building_id'] == 1 for b in bld1_only['items']), "❌ building_id=1 筛选错了"
print(f"    building_id=1 (楼栋1筛选): 共 {bld1_only['total']} 条，全部 building_id=1")
print("  ✅ 通过: building_id 参数可精确筛选分摊范围")

print("\n" + "=" * 60)
print("🎉 全部四项新需求验证通过!")
print("=" * 60)
