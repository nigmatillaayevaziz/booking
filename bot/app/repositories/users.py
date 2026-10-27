from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import PIICipher
from app.models.entities import Role, User, UserRole
from app.models.enums import Language, RoleCode


class UserRepository:
    def __init__(self, session: AsyncSession, cipher: PIICipher) -> None:
        self.session = session
        self.cipher = cipher

    async def by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.tg_id == telegram_id))

    async def ensure_user(self, telegram_id: int, full_name: str, language: str = "uz") -> User:
        user = await self.by_telegram_id(telegram_id)
        if user is not None:
            return user
        user = User(
            tg_id=telegram_id,
            full_name_encrypted=self.cipher.encrypt(full_name),
            phone_encrypted=None,
            language=Language(language),
        )
        self.session.add(user)
        await self.session.flush()
        passenger_role = await self.session.scalar(select(Role).where(Role.code == RoleCode.PASSENGER))
        if passenger_role:
            self.session.add(UserRole(user_id=user.id, role_id=passenger_role.id))
        return user

    async def roles(self, user_id: int) -> set[str]:
        rows = await self.session.scalars(
            select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
        return {item.value for item in rows}

    async def grant_role(self, user_id: int, role_code: RoleCode, granted_by: int | None = None) -> None:
        role = await self.session.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise ValueError(f"Role seed topilmadi: {role_code.value}")
        existing = await self.session.get(UserRole, (user_id, role.id))
        if existing is None:
            self.session.add(UserRole(user_id=user_id, role_id=role.id, granted_by=granted_by))
