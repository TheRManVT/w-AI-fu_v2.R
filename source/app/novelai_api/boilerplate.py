from logging import Logger, StreamHandler
from os import environ as env
from typing import Optional

from aiohttp import ClientSession

from novelai_api import NovelAIAPI


class API:
    _token: str
    _session: ClientSession

    logger: Logger
    api: Optional[NovelAIAPI]

    def __init__(self):
        if "NAI_TOKEN" not in env:
            raise RuntimeError("Please ensure that NAI_TOKEN is set in your environment")

        self._token = env["NAI_TOKEN"]

        self.logger = Logger("NovelAI")
        self.logger.addHandler(StreamHandler())

        self.api = NovelAIAPI(logger=self.logger)

    async def __aenter__(self):
        self._session = ClientSession()
        await self._session.__aenter__()

        self.api.attach_session(self._session)
        await self.api.high_level.login_with_token(self._token)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)