from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Todo
from app.schemas.todo import TodoFilter, TodoListResponse
from app.utils.timezone import KST


def _kst_today_range() -> tuple[datetime, datetime]:
    """Return (start, end) of today in KST as UTC-aware datetimes."""
    now_kst = datetime.now(KST)
    start = datetime.combine(now_kst.date(), time.min, tzinfo=KST)
    end = datetime.combine(now_kst.date(), time.max, tzinfo=KST)
    return start, end


async def list_todos(
    db: AsyncSession,
    pharmacy_id: int,
    filter: TodoFilter,
    sort: str,
    limit: int,
    offset: int,
) -> TodoListResponse:
    base = select(Todo).where(Todo.pharmacy_id == pharmacy_id)

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

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    if sort == "due_date":
        base = base.order_by(Todo.due_date.asc().nullslast(), Todo.sort_order.asc())
    elif sort == "priority":
        base = base.order_by(Todo.priority.asc(), Todo.due_date.asc().nullslast())
    else:
        base = base.order_by(Todo.created_at.desc())

    result = await db.execute(base.limit(limit).offset(offset))
    items = result.scalars().all()

    return TodoListResponse(items=items, total=total)


async def get_todo(db: AsyncSession, todo_id: int, pharmacy_id: int) -> Todo | None:
    result = await db.execute(
        select(Todo).where(
            and_(Todo.id == todo_id, Todo.pharmacy_id == pharmacy_id)
        )
    )
    return result.scalar_one_or_none()


async def create_todo(
    db: AsyncSession, pharmacy_id: int, title: str, user_id: int,
    description: str | None = None, due_date: datetime | None = None,
    priority: int = 4,
) -> Todo:
    todo = Todo(
        pharmacy_id=pharmacy_id,
        title=title,
        description=description,
        due_date=due_date,
        priority=priority,
        created_by=user_id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


async def update_todo(
    db: AsyncSession, todo: Todo, update_data: dict,
) -> Todo:
    for key, value in update_data.items():
        setattr(todo, key, value)
    todo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()


async def toggle_complete(db: AsyncSession, todo: Todo, user_id: int) -> Todo:
    if todo.is_completed:
        todo.is_completed = False
        todo.completed_at = None
        todo.completed_by = None
    else:
        todo.is_completed = True
        todo.completed_at = datetime.now(timezone.utc)
        todo.completed_by = user_id
    todo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(todo)
    return todo


async def reschedule_todo(
    db: AsyncSession, todo: Todo, due_date: datetime | None,
) -> Todo:
    todo.due_date = due_date
    todo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(todo)
    return todo
