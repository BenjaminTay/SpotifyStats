"""Account center API — aggregated endpoints for the /account page."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.services.account_service import get_account_summary, get_collection_insights

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("")
def account_summary(conn: Connection = Depends(get_conn)):
    """聚合账号中心所有数据（library + search + insights + podcast + video + profile + collection insights）。"""
    return get_account_summary(conn)


@router.get("/collection-insights")
def collection_insights(conn: Connection = Depends(get_conn)):
    """收藏×播放交叉分析洞察。"""
    return get_collection_insights(conn)
