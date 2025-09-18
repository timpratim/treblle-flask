# coding=utf-8

"""
treblle_flask.telemetry_publisher
~~~~~~~~~~~~~~~~~~~~~~~

This module implements the TelemetryPublisher class, which is responsible for asynchronously
publishing telemetry to Treblle backend.

You shouldn't use this class directly, instead use Treblle class from the extension module.
"""

from aiohttp import ClientSession
from asyncio import new_event_loop, run_coroutine_threadsafe, set_event_loop
from itertools import cycle
from logging import getLogger
from threading import Thread

logger = getLogger('treblle')


class TelemetryPublisher:
    _instance = None
    BACKEND_HOSTS = [
        'https://rocknrolla.treblle.com',
        'https://punisher.treblle.com',
        'https://sicario.treblle.com',
    ]
    TIMEOUT_SECONDS = 2

    def __init__(self, treblle_sdk_token, treblle_api_key, custom_url=None):
        """
        Asynchronously publishes telemetry to Treblle backend in a round-robin fashion.

        You shouldn't use this class directly, instead use Treblle class from the extension module.
        """

        self._treblle_sdk_token = treblle_sdk_token
        self._treblle_api_key = treblle_api_key
        
        if custom_url:
            self._hosts_cycle = cycle([custom_url])
        else:
            self._hosts_cycle = cycle(self.BACKEND_HOSTS)
        self._session = None

        self._event_loop = new_event_loop()
        self._publisher_thread = Thread(target=self._run_event_loop)
        self._publisher_thread.start()

    def _run_event_loop(self):
        set_event_loop(self._event_loop)
        self._event_loop.run_until_complete(self._init_session())
        self._event_loop.run_forever()

    async def _init_session(self):
        self._session = await ClientSession().__aenter__()

    async def _close_session(self):
        if self._session:
            await self._session.__aexit__(None, None, None)
            self._session = None

    async def _process_request(self, payload):
        try:
            host_url = next(self._hosts_cycle)
            logger.debug(f'Treblle: Sending telemetry to {host_url}')
            import gzip
            import json
            
            # Compress payload with GZIP as required by Treblle
            json_data = json.dumps(payload).encode('utf-8')
            compressed_data = gzip.compress(json_data)
            
            response = await self._session.post(
                url=host_url, data=compressed_data, timeout=self.TIMEOUT_SECONDS,
                headers={
                    'X-API-Key': self._treblle_sdk_token,
                    'Content-Type': 'application/json',
                    'Content-Encoding': 'gzip'
                }
            )
            response_text = await response.text()
            logger.debug(f'Treblle: Response status: {response.status}')
            logger.debug(f'Treblle: Response body: {response_text}')
            if response.status >= 300:
                logger.warning(f'Treblle API error {response.status}: {response_text}')
            elif response.status == 200:
                if 'error' in response_text.lower() or 'invalid' in response_text.lower():
                    logger.warning(f'Treblle: 200 OK but with error message: {response_text}')
                else:
                    logger.info('Treblle: Request accepted successfully')
        except Exception as e:
            logger.debug(f'Failed to send telemetry: {e.__class__.__name__}{e.args}')

    def send_to_treblle(self, payload):
        future = run_coroutine_threadsafe(self._process_request(payload), self._event_loop)
        # Wait a short time to get the response for debugging
        try:
            future.result(timeout=3)  # Wait up to 3 seconds for response
        except Exception as e:
            logger.warning(f'Treblle: Request failed: {e}')

    def teardown(self):
        if self._session:
            run_coroutine_threadsafe(self._close_session(), self._event_loop).result()
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            self._publisher_thread.join()

    def __del__(self):
        self.teardown()
