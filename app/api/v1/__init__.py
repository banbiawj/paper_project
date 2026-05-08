# app/api/v1/__init__.py
from fastapi import APIRouter
from app.api.v1.endpoints import analyse,inquire,DataOperate,DisplayContent,admin

api_router = APIRouter()
# api_router.include_router(file.router, prefix="/file", tags=["file"])
api_router.include_router(analyse.router, prefix="/document", tags=["analyse"])
api_router.include_router(inquire.router, prefix="/inquire", tags=["inquire"])
api_router.include_router(DataOperate.router, prefix="/DataOperate", tags=["DataOperate"])
api_router.include_router(DisplayContent.router, prefix="/DisplayContent", tags=["DisplayContent"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

