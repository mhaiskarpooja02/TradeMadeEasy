# =============================================================================
# AngelOrderClient (REST Based - Production Safe)
# =============================================================================

import httpx
import time
import pyotp
from typing import Optional

from config.TradeFriendSettings import api_key, username, pin, totp_qr
from utils.logger import get_angel_rest_logger

BASE_URL = "https://apiconnect.angelone.in"


class AngelOrderClient:

    def __init__(self):
        self.logger = get_angel_rest_logger()

        self.api_key = api_key
        self.client_id = username
        self.password = pin
        self.totp_secret = totp_qr

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None

        self.client = httpx.Client(timeout=15)

        self.logger.info("AngelOrderClient initialized")

    # ==========================================================================
    # Generate TOTP
    # ==========================================================================
    def _generate_totp(self) -> str:
        return pyotp.TOTP(self.totp_secret).now()

    # ==========================================================================
    # Login
    # ==========================================================================
    def login(self):

        url = f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"

        payload = {
            "clientcode": self.client_id,
            "password": self.password,
            "totp": self._generate_totp()
        }

        headers = self._base_headers()

        self.logger.info("🔐 Logging in to Angel...")

        start = time.perf_counter()
        response = self.client.post(url, json=payload, headers=headers)
        latency = (time.perf_counter() - start) * 1000

        self.logger.info(f"⏱ Login latency: {latency:.2f} ms")
        self.logger.info(f"📥 Raw login response: {response.text}")

        data = response.json()

        if not data.get("status"):
            raise Exception(f"Login failed: {data}")

        self.access_token = data["data"]["jwtToken"]
        self.refresh_token = data["data"]["refreshToken"]
        self.feed_token = data["data"]["feedToken"]

        self.logger.info("✅ Angel login successful")

    # ==========================================================================
    # Place Order
    # ==========================================================================
    def place_order(self, payload: dict) -> str:

        if not self.access_token:
            self.login()

        endpoint = "/rest/secure/angelbroking/order/v1/placeOrder"

        response = self._post(endpoint, payload)

        if not response:
            raise Exception("Empty response from Angel")

        if not response.get("status"):
            raise Exception(f"Order rejected: {response}")

        data = response.get("data")

        if not data or "orderid" not in data:
            raise Exception(f"Invalid order response: {response}")

        order_id = data["orderid"]

        self.logger.info(f"✅ Order placed successfully → {order_id}")

        return order_id

    # ==========================================================================
    # POST With Retry
    # ==========================================================================
    def _post(self, endpoint: str, payload: dict, retry=True):

        url = f"{BASE_URL}{endpoint}"
        headers = self._auth_headers()

        start = time.perf_counter()
        response = self.client.post(url, json=payload, headers=headers)
        latency = (time.perf_counter() - start) * 1000

        self.logger.info(f"🚀 POST {endpoint}")
        self.logger.info(f"📤 Payload: {payload}")
        self.logger.info(f"⏱ Latency: {latency:.2f} ms")
        self.logger.info(f"📥 Raw response: {response.text}")

        try:
            data = response.json()
        except Exception:
            raise Exception(f"Non-JSON response: {response.text}")

        if not data.get("status") and retry:
            message = str(data.get("message", "")).lower()

            if "token" in message or "session" in message:
                self.logger.warning("♻️ Token expired. Re-login & retrying once...")
                self.login()
                return self._post(endpoint, payload, retry=False)

        return data

    # ==========================================================================
    # Headers
    # ==========================================================================
    def _base_headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key
        }

    def _auth_headers(self):
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    # ==========================================================================
    # Close Session
    # ==========================================================================
    def close(self):
        try:
            self.client.close()
            self.logger.info("Angel HTTP session closed")
        except Exception:
            pass