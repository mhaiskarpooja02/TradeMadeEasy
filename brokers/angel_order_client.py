# =============================================================================
# AngelOrderClient (REST Based - Production Safe)
# =============================================================================

import httpx
import time
import pyotp
from typing import Optional
import uuid

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

        order_id = data.get("orderid")
        unique_order_id = data.get("uniqueorderid")
    
        if not order_id or not unique_order_id:
            raise Exception(f"Incomplete order response: {response}")
    
        self.logger.info(
            f"✅ Order placed successfully → "
            f"OrderID={order_id} | UniqueID={unique_order_id}"
        )
    
        return {
            "order_id": order_id,
            "unique_order_id": unique_order_id
        }


    # ==========================================================================
    # Get Individual Order Status
    # ==========================================================================
    def get_order_status(self, unique_order_id: str) -> dict:

        if not self.access_token:
            self.login()

        endpoint = f"/rest/secure/angelbroking/order/v1/details/{unique_order_id}"

        response = self._get(endpoint)

        if not response:
            raise Exception("Empty response from Angel")

        if not response.get("status"):
            raise Exception(f"Order status fetch failed: {response}")

        data = response.get("data")

        if not data:
            raise Exception(f"Invalid order status response: {response}")

        self.logger.info(
            f"✅ Order status fetched successfully "
            f"| UniqueID={unique_order_id}"
        )
        return data

    
    # ==========================================================================
    # POST With Retry
    # ==========================================================================
    def _post(self, endpoint: str, payload: dict, retry=True):
    
        request_id = uuid.uuid4().hex[:6]
    
        url = f"{BASE_URL}{endpoint}"
        headers = self._auth_headers()
    
        self.logger.info(f"[REQ={request_id}] 🚀 POST {endpoint}")
        self.logger.info(f"[REQ={request_id}] 📤 Payload: {payload}")
    
        start = time.perf_counter()
        response = self.client.post(url, json=payload, headers=headers)
        latency = (time.perf_counter() - start) * 1000
    
        self.logger.info(f"[REQ={request_id}] ⏱ Latency: {latency:.2f} ms")
        self.logger.info(f"[REQ={request_id}] 📥 Raw response: {response.text}")
    
        try:
            data = response.json()
        except Exception:
            raise Exception(
                f"[REQ={request_id}] Non-JSON response: {response.text}"
            )
    
        # -----------------------------------------
        # Token Expiry Handling
        # -----------------------------------------
        if not data.get("status") and retry:
            message = str(data.get("message", "")).lower()
    
            if "token" in message or "session" in message:
                self.logger.warning(
                    f"[REQ={request_id}] ♻️ Token expired. "
                    f"Re-login & retrying once..."
                )
                self.login()
                return self._post(endpoint, payload, retry=False)
    
        return data

    # ==========================================================================
    # GET With Retry
    # ==========================================================================
    def _get(self, endpoint: str, retry=True):

        request_id = uuid.uuid4().hex[:6]

        url = f"{BASE_URL}{endpoint}"
        headers = self._auth_headers()

        self.logger.info(f"[REQ={request_id}] 🔎 GET {endpoint}")

        start = time.perf_counter()
        response = self.client.get(url, headers=headers)
        latency = (time.perf_counter() - start) * 1000

        self.logger.info(f"[REQ={request_id}] ⏱ Latency: {latency:.2f} ms")
        self.logger.info(f"[REQ={request_id}] 📥 Raw response: {response.text}")

        try:
            data = response.json()
        except Exception:
            raise Exception(
                f"[REQ={request_id}] Non-JSON response: {response.text}"
            )

        # -----------------------------------------
        # Token Expiry Handling
        # -----------------------------------------
        if not data.get("status") and retry:
            message = str(data.get("message", "")).lower()

            if "token" in message or "session" in message:
                self.logger.warning(
                    f"[REQ={request_id}] ♻️ Token expired. "
                    f"Re-login & retrying once..."
                )
                self.login()
                return self._get(endpoint, retry=False)

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