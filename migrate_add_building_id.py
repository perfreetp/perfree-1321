import sqlite3

db_path = "smart_energy_park.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE bills ADD COLUMN building_id INTEGER")
    print("✅ bills 表已添加 building_id 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️  building_id 列已存在，跳过")
    else:
        print(f"❌ 错误: {e}")

conn.commit()
conn.close()
print("完成")
