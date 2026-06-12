from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import engine, Base
from app.models import models
from app.api import auth, park, energy, quota, carbon, operation, report

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="智慧能源园区用能与碳账后端服务 - 为园区门户、物业系统和企业自助端提供能源数据管理能力",
    version="1.0.0",
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["系统"])
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0"}


app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["认证与用户"])
app.include_router(park.router, prefix=settings.API_V1_PREFIX, tags=["园区档案"])
app.include_router(energy.router, prefix=settings.API_V1_PREFIX, tags=["能耗管理"])
app.include_router(quota.router, prefix=settings.API_V1_PREFIX, tags=["定额与异常"])
app.include_router(carbon.router, prefix=settings.API_V1_PREFIX, tags=["碳排与预测"])
app.include_router(operation.router, prefix=settings.API_V1_PREFIX, tags=["设备与需求响应"])
app.include_router(report.router, prefix=settings.API_V1_PREFIX, tags=["账单与报告"])
