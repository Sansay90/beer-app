"""Поток вкладок: публикация из потоков журнала и напоминаний доходит до вкладки в цикле событий сервиса."""
import asyncio

from app.brewery.streams import Streams


def test_publish_from_another_thread():
    async def main():
        streams = Streams(asyncio.get_running_loop())
        with streams.subscribe("u1") as q:
            await asyncio.to_thread(streams.brew, "u1", "b1")
            await asyncio.to_thread(streams.notice, "u2")              # чужой вкладке — не нам
            assert await asyncio.wait_for(q.get(), 1) == {"type": "brew", "data": {"id": "b1"}}
            assert q.empty()

    asyncio.run(main())
