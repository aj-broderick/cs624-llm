import datetime
import logging
import os
from typing import List, Optional

from bytewax.inputs import DynamicInput, StatelessSource
import requests

logger = logging.getLogger()


class AlpacaNewsBatchInput(DynamicInput):
    """Input class to receive batch news data
    from the Alpaca news RESTful API.

    Args:
        tickers: list - should be a list of tickers, use "*" for all
    """

    def __init__(self, tickers: List[str], from_datetime: datetime.datetime, to_datetime: datetime.datetime):
        self._tickers = tickers
        self._from_datetime = from_datetime
        self._to_datetime = to_datetime

    # distribute the tickers to the workers. If parallelized
    # workers will establish their own websocket connection and
    # subscribe to the tickers they are allocated
    def build(self, worker_index, worker_count):
        prods_per_worker = int(len(self._tickers) / worker_count)
        worker_tickers = self._tickers[
            int(worker_index * prods_per_worker) : int(
                worker_index * prods_per_worker + prods_per_worker
            )
        ]

        return AlpacaNewsBatchSource(
            tickers=worker_tickers,
            from_datetime=self._from_datetime,
            to_datetime=self._to_datetime,
            )


class AlpacaNewsBatchSource(StatelessSource):
    def __init__(self, tickers: List[str], from_datetime: datetime.datetime, to_datetime: datetime.datetime):
        self._alpaca_client = build_alpaca_client(
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            tickers=tickers
            )

    def next(self):
        news = self._alpaca_client.recv()
        
        if news is None:
            raise StopIteration()
        
        return news

    def close(self):
        pass
    

def build_alpaca_client(
    from_datetime: datetime.datetime,
    to_datetime: datetime.datetime,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    tickers: Optional[List[str]] = None,
) -> "AlpacaNewsBatchClient":
    if api_key is None:
        try:
            api_key = os.environ["ALPACA_API_KEY"]
        except KeyError:
            raise KeyError(
                "ALPACA_API_KEY must be set as environment variable or manually passed as an argument."
            )

    if api_secret is None:
        try:
            api_secret = os.environ["ALPACA_API_SECRET"]
        except KeyError:
            raise KeyError(
                "ALPACA_API_SECRET must be set as environment variable or manually passed as an argument."
            )

    if tickers is None:
        tickers = ["*"]

    return AlpacaNewsBatchClient(
        from_datetime=from_datetime, to_datetime=to_datetime, api_key=api_key, api_secret=api_secret, tickers=tickers
    )


class AlpacaNewsBatchClient:
    """Alpaca News API Client that uses a RESTful API to fetch news data."""

    NEWS_URL = "https://data.alpaca.markets/v1beta1/news"

    def __init__(
        self,
        from_datetime: datetime.datetime,
        to_datetime: datetime.datetime,
        api_key: str,
        api_secret: str,
        tickers: List[str],
    ):
        self._from_datetime = from_datetime
        self._to_datetime = to_datetime
        self._api_key = api_key
        self._api_secret = api_secret
        self._tickers = tickers
        
        self._page_token = None
        self._first_request = True
        
    @property
    def try_request(self) -> bool:
        return self._first_request or self._page_token is not None 
        
    def recv(self):
        """
        Convenience function to fetch a batch of news from Alpaca API
        """
        
        if not self.try_request:
            return None
        
        self._first_request = False
        
        # prepare the request URL
        headers = {
            "Apca-Api-Key-Id": self._api_key,
            "Apca-Api-Secret-Key": self._api_secret,
        }
        
        params = {
            "start": self._from_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": self._to_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 50,
            "include_content": True,
            "sort": "ASC",
        }
        if self._page_token is not None:
            params["page_token"] = self._page_token

        response = requests.get(self.NEWS_URL, headers=headers, params=params)

        # parse output
        next_page_token = None
        if response.status_code == 200:  # Check if the request was successful
            # parse response into json
            news_json = response.json()

            # extract next page token (if any)
            next_page_token = news_json.get("next_page_token", None)

        else:
            logger.error("Request failed with status code:", response.status_code)
            
        self._page_token = next_page_token

        return news_json["news"]


if __name__ == "__main__":
    from streaming_pipeline import initialize
    initialize()
    
    client = build_alpaca_client(datetime.datetime.now() - datetime.timedelta(days=10), datetime.datetime.now())
    client.recv()
