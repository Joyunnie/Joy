from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import Todo, User
from app.schemas.todo import (
    TodoCreate,
    TodoFilter,
    TodoListResponse,
    TodoReschedule,
    TodoResponse,
    TodoUpdate,
)

router = APIRouter()

KST = timezone(timedelta(hours=9))


def _kst_today_range() -> tuple[datetime, datetime]:
    """Return (start, end) of today in KST as UTC-aware datetimes."""
    now_kst = datetime.now(KST)
    start = datetime.combine(now_kst.date(), time.min, tzinfo=KST)
    end = datetime.combine(now_kst.date(), time.max, tzinfo=KST)
    return start, end


@router.get("", response_model=TodoListResponse)
async def list_todos(
    user: User = Depends(get_current_user),
    filter: TodoFilter = Query("all"),
    sort: str = Query("due_date"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    base = select(Todo).where(Todo.pharmacy_id == user.pharmacy_id)

    today_start, today_end = _kst_today_range()

    if filter == "today":
        base = base.where(
            and_(
                Todo.due_date >= today_start,
                Todo.due_date <= today_end,
                Todo.is_completed == False,
            )
        )
    elif filter == "upcoming":
        base = base.where(
            and_(Todo.due_date > today_end, Todo.is_completed == False)
        )
    elif filter == "overdue":
        base = base.where(
            and_(Todo.due_date < today_start, Todo.is_completed == False)
        )
    elif filter == "no_date":
        base = base.where(
            and_(Todo.due_date.is_(None), Todo.is_completed == False)
        )
    elif filter == "completed":
        base = base.where(Todo.is_completed == True)

    # count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # sort
    sort_col_map = {
        "due_date": Todo.due_date,
        "priority": Todo.priority,
        "created_at": Todo.created_at,
    }
    sort_col = sort_col_map.get(sort, Todo.due_date)
    if sort == "due_date":
        base = base.order_by(Todo.due_date.asc().nullslast(), Todo.sort_order.asc())
    elif sort == "priority":
        base = base.order_by(Todo.priority.asc(), Todo.due_date.asc().nullslast())
    else:
        base = base.order_by(Todo.created_at.desc())

    result = await db.execute(base.limit(limit).offset(offset))
    items = result.scalars().all()

    return TodoListResponse(items=items, total=total)


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(
    body: TodoCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = Todo(
        pharmacy_id=user.pharmacy_id,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        priority=body.priority,
        created_by=user.id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_todo_or_404(db, todo_id, user.pharmacy_id)
    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int,
    body: TodoUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_todo_or_404(db, todo_id, user.pharmacy_id)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(todo, key, value)
    todo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(todo)
    return todo


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(
    todo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_todo_or_404(db, todo_id, user.pharmacy_id)
    await db.delete(todo)
    await db.flush()


@router.patch("/{todo_id}/complete", response_model=TodoResponse)
async def toggle_complete(
    todo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_todo_or_404(db, todo_id, user.pharmacy_id)
    if todo.is_completed:
        todo.is_completed = False
        todo.completed_at = None
        todo.completed_by = None
    else:
        todo.is_completed = True
        todo.completed_at = datetime.now(timezone.utc)
        todo.completed_by = user.id
    todo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(todo)
    return todo


@router.patch("/{todo_id}/reschedule", response_model=TodoResponse)
async def reschedule_todo(
    todo_id: int,
    body: TodoReschedule,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_todo_or_404(db, todo_id, user.pharmacy_id)
    todo.due_date = body.due_date
    todo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(todo)
    return todo


async def _get_todo_or_404(
    db: AsyncSession, todo_id: int, pharmacy_id: int
) -> Todo:
    result = await db.execute(
        select(Todo).where(
            and_(Todo.id == todo_id, Todo.pharmacy_id == pharmacy_id)
        )
    )
    todo = result.scalar_one_or_none()
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found"
        )
    return todo
