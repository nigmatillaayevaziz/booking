from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditLog, PriceHistory, Route, RouteFare
from app.services.pricing import RoutePrices


async def set_route_fares(
    session: AsyncSession,
    *,
    route_id: int,
    prices: RoutePrices,
    actor_id: int,
    request_id: str,
) -> RouteFare:
    prices.validate()
    route = await session.scalar(select(Route).where(Route.id == route_id).with_for_update())
    if route is None:
        raise ValueError("Marshrut topilmadi")
    fare = await session.scalar(select(RouteFare).where(RouteFare.route_id == route_id).with_for_update())
    before = None
    if fare is None:
        fare = RouteFare(route_id=route_id, changed_by=actor_id)
        session.add(fare)
    else:
        before = {"taxi": fare.taxi_price, "bus": fare.bus_price, "train": fare.train_price}
    after = {"taxi": prices.taxi, "bus": prices.bus, "train": prices.train}
    fare.taxi_price = prices.taxi
    fare.bus_price = prices.bus
    fare.train_price = prices.train
    fare.changed_by = actor_id
    await session.flush()
    session.add_all([
        PriceHistory(
            route_id=route_id,
            old_prices=before,
            new_prices=after,
            changed_by=actor_id,
        ),
        AuditLog(
            actor_id=actor_id,
            action="route_fares.updated",
            entity="route_fares",
            entity_id=str(fare.id),
            before=before,
            after=after,
            request_id=request_id,
        ),
    ])
    return fare
