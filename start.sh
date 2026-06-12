#!/bin/bash
echo "============================================"
echo "  智慧能源园区用能与碳账后端服务"
echo "============================================"
echo ""

if [ ! -d "venv" ]; then
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv venv
fi

echo "[2/3] 激活虚拟环境并安装依赖..."
source venv/bin/activate
pip install -r requirements.txt

if [ ! -f "smart_energy_park.db" ]; then
    echo "[3/3] 初始化数据库..."
    python init_db.py
fi

echo ""
echo "启动服务..."
echo "文档地址: http://127.0.0.1:8000/docs"
echo ""
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
