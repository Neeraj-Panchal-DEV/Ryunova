from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import RyunovaProductMaster
from app.org_access import OrganisationContextDep

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def dashboard_summary(
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> dict:
    q = select(func.count()).select_from(RyunovaProductMaster).where(RyunovaProductMaster.active.is_(True))
    if ctx.organisation_id is not None:
        q = q.where(RyunovaProductMaster.organisation_id == ctx.organisation_id)
    total = int(db.scalar(q) or 0)
    return {"active_products": total}
