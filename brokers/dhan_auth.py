import requests
import webbrowser
from utils.logger import get_logger
from config.settings import api_key, api_secret
import json
from pathlib import Path

logger = get_logger(__name__)
TOKEN_FILE = Path("config/dhan_token.json")

class DhanAuthManager:
    def __init__(self):
        self.api_key = api_key
        self.api_secret = api_secret

    def generate_consent(self):
        """Step 1: Generate consentAppId"""
        url = f"https://auth.dhan.co/app/generate-consent?client_id={self.api_key}"
        headers = {"app_id": self.api_key, "app_secret": self.api_secret}

        res = requests.post(url, headers=headers)
        res.raise_for_status()
        data = res.json()

        if data.get("status") != "success":
            raise Exception(f"Consent generation failed: {data}")

        consent_id = data["consentAppId"]
        logger.info(f"ConsentAppId generated: {consent_id}")
        return consent_id

    def open_login_and_get_tokenid(self, consent_id):
        """Step 2: Open browser for login"""
        login_url = f"https://auth.dhan.co/login/consentApp-login?consentAppId={consent_id}"
        print(f"\n🔑 Open this URL in browser to login: {login_url}\n")
        webbrowser.open(login_url)
        token_id = input("Paste the tokenId from redirected URL: ").strip()
        return token_id

    def consume_consent(self, token_id):
        """Step 3: Consume consent and get access token"""
        url = f"https://auth.dhan.co/app/consumeApp-consent?tokenId={token_id}"
        headers = {"app_id": self.api_key, "app_secret": self.api_secret}

        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        logger.info("Access token generated successfully.")
        return data

    def generate_and_store_token(self):
        """Main function: generate and save token"""
        consent_id = self.generate_consent()
        token_id = self.open_login_and_get_tokenid(consent_id)
        token_data = self.consume_consent(token_id)

        TOKEN_FILE.parent.mkdir(exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f, indent=4)
        logger.info("Access token saved to dhan_token.json")
        print("\n✅ Access token saved to config/dhan_token.json")
        return token_data
