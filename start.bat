fastapi uvicorn

@echo off
chcp 65001 >nul
echo ============================================
echo   智慧能源园区用能与碳账后端服务
echo ============================================
echo.

if not exist "venv" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
)

echo [2/3] 激活虚拟环境并安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt

if not exist "smart_energy_park.db" (
    echo [3/3] 初始化数据库...
    python init_db.py
)

echo.
echo 启动服务...
echo 文档地址: http://127.0.0.1:8000/docs
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
