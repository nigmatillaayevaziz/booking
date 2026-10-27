"""Initial production schema.

Revision ID: 0001
Revises:
"""

from alembic import op

from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    op.execute(
        """
        INSERT INTO roles (id, code) VALUES
          (1, 'passenger'), (2, 'driver'), (3, 'operator'), (4, 'admin'), (5, 'super_admin')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO transport_types
          (id, code, name_uz, name_ru, commission_pct, max_passengers_per_booking, created_at, updated_at)
        VALUES
          (1, 'taxi', 'Taxi', 'Такси', 10, 4, now(), now()),
          (2, 'bus', 'Avtobus', 'Автобус', 7, 5, now(), now()),
          (3, 'train', 'Poyezd', 'Поезд', 5, 5, now(), now())
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO regions (id, name_uz, name_ru, is_active, sort_order, created_at, updated_at) VALUES
          (1, 'Toshkent shahri', 'Город Ташкент', true, 1, now(), now()),
          (2, 'Toshkent viloyati', 'Ташкентская область', true, 2, now(), now()),
          (3, 'Andijon', 'Андижан', true, 3, now(), now()),
          (4, 'Buxoro', 'Бухара', true, 4, now(), now()),
          (5, 'Farg‘ona', 'Фергана', true, 5, now(), now()),
          (6, 'Jizzax', 'Джизак', true, 6, now(), now()),
          (7, 'Qashqadaryo', 'Кашкадарья', true, 7, now(), now()),
          (8, 'Navoiy', 'Навои', true, 8, now(), now()),
          (9, 'Namangan', 'Наманган', true, 9, now(), now()),
          (10, 'Samarqand', 'Самарканд', true, 10, now(), now()),
          (11, 'Sirdaryo', 'Сырдарья', true, 11, now(), now()),
          (12, 'Surxondaryo', 'Сурхандарья', true, 12, now(), now()),
          (13, 'Xorazm', 'Хорезм', true, 13, now(), now()),
          (14, 'Qoraqalpog‘iston Respublikasi', 'Республика Каракалпакстан', true, 14, now(), now())
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
