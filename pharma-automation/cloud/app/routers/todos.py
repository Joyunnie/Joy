from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.todo import (
    TodoCreate,
    TodoFilter,
    TodoListResponse,
    TodoReschedule,
    TodoResponse,
    TodoUpdate,
)
from app.services import todo_service

router = APIRouter()


@router.get("", response_model=TodoListResponse)
async def list_todos(
    user: User = Depends(get_current_user),
    filter: TodoFilter = Query("all"),
    sort: str = Query("due_date"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await todo_service.list_todos(
        db, user.pharmacy_id, filter, sort, limit, offset,
    )


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(
    body: TodoCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await todo_service.create_todo(
        db, user.pharmacy_id, body.title, user.id,
        description=body.description, due_date=body.due_date, priority=body.priority,
    )


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_or_404(db, todo_id, user.pharmacy_id)
    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int,
    body: TodoUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_or_404(db, todo_id, user.pharmacy_id)
    return await todo_service.update_todo(
        db, todo, body.model_dump(exclude_unset=True),
    )


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(
    todo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_or_404(db, todo_id, user.pharmacy_id)
    await todo_service.delete_todo(db, todo)


@router.patch("/{todo_id}/complete", response_model=TodoResponse)
async def toggle_complete(
    todo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_or_404(db, todo_id, user.pharmacy_id)
    return await todo_service.toggle_complete(db, todo, user.id)


@router.patch("/{todo_id}/reschedule", response_model=TodoResponse)
async def reschedule_todo(
    todo_id: int,
    body: TodoReschedule,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = await _get_or_404(db, todo_id, user.pharmacy_id)
    return await todo_service.reschedule_todo(db, todo, body.due_date)


async def _get_or_404(db: AsyncSession, todo_id: int, pharmacy_id: int):
    todo = await todo_service.get_todo(db, todo_id, pharmacy_id)
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found",
        )
    return todo
