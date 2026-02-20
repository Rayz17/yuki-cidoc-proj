from fastapi import APIRouter
from src.api.routes import router as general_router
from src.api.tasks import router as tasks_router
from src.api.master import router as master_router
from src.api.agents import router as agents_router
from src.api.db_tools import router as db_router

router = APIRouter()
router.include_router(general_router, tags=["General"])
router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
router.include_router(master_router, prefix="/master", tags=["Master Data"])
router.include_router(agents_router, prefix="/agents", tags=["Agent Management"])
router.include_router(db_router, prefix="/db", tags=["Database Tools"])
