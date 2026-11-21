import asyncio
import logging

import httpx


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True,
)

logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)


async def main() -> None:
    url = "https://war-thunder-api.onrender.com/sqb_team/nashi"

    print("API_TEST: файл запущен", flush=True)
    logging.warning("API_TEST: начинаю запрос %s", url)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=20.0),
        ) as client:
            response = await client.get(url)

            logging.warning(
                "API_TEST: статус=%s, тело=%r",
                response.status_code,
                response.text[:1000],
            )

            response.raise_for_status()

    except Exception:
        logging.exception("API_TEST: запрос завершился ошибкой")
        raise


if __name__ == "__main__":
    asyncio.run(main())
