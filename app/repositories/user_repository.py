import uuid as uuid_pkg

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import DepartmentEnum, RoleEnum, User


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(
    db: AsyncSession,
    user_id: uuid_pkg.UUID,
) -> User | None:
    result = await db.execute(
        select(User).where(User.uuid == str(user_id))
    )
    return result.scalar_one_or_none()


async def get_user_by_phone_number(
    db: AsyncSession,
    phone_number: str,
) -> User | None:
    result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    **kwargs,
) -> User:
    user = User(**kwargs)
    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


async def get_users(
    db: AsyncSession,
    search: str | None,
    department: DepartmentEnum | None,
    page: int,
    size: int,
) -> tuple[list[User], int]:
    conditions = []

    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                User.email.ilike(search_pattern),
                User.name.ilike(search_pattern),
            )
        )

    if department:
        conditions.append(User.department == department)

    count_query = (
        select(func.count())
        .select_from(User)
        .where(*conditions)
    )
    total = await db.scalar(count_query)

    users_query = (
        select(User)
        .where(*conditions)
        .order_by(User.name.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(users_query)
    users = list(result.scalars().all())

    return users, total or 0


async def update_user_role(
    db: AsyncSession,
    user: User,
    role: RoleEnum,
) -> User:
    user.role = role

    await db.commit()
    await db.refresh(user)

    return user


async def update_user_info(
    db: AsyncSession,
    user: User,
    department: DepartmentEnum | None,
    phone_number: str | None,
) -> User:
    if department is not None:
        user.department = department

    if phone_number is not None:
        user.phone_number = phone_number

    await db.commit()
    await db.refresh(user)

    return user


async def update_user_password(
    db: AsyncSession,
    user: User,
    hashed_password: str,
) -> None:
    user.hashed_password = hashed_password
    await db.commit()


async def delete_user(
    db: AsyncSession,
    user: User,
) -> None:
    await db.delete(user)
    await db.commit()

async def count_active_admins(
    db: AsyncSession,
) -> int:
    query = (
        select(func.count())
        .select_from(User)
        .where(
            User.role == RoleEnum.ADMIN,
            User.is_active.is_(True),
        )
    )
    count = await db.scalar(query)
    return count or 0