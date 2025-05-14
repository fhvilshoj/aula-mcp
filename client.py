"""
Aula client for MCP implementation
"""

import base64
import datetime
import json
import logging
import pickle
from typing import Any, Dict, List, Optional, Tuple

import pytz
import requests
from bs4 import BeautifulSoup

from const import API_BASE, API_VERSION, LOGIN_URL, Features
from models.base import AulaChild, AulaConfig, AulaProfile, AulaSession, AulaToken
from session_cache import SessionCache

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication failures"""

    pass


class AulaClient:
    """Client for interacting with the Aula API"""

    def __init__(self, config: AulaConfig):
        """Initialize the Aula client"""
        self.config = config
        self._session = None
        self._api_url = f"{API_BASE}{API_VERSION}"
        self.session_data = AulaSession(api_url=self._api_url)
        self.session_cache = SessionCache()

        # Child data
        self._children: List[AulaChild] = []
        self._child_names: Dict[str, str] = {}
        self._child_ids: List[str] = []
        self._child_user_ids: List[str] = []
        self._institutions: Dict[str, str] = {}
        self._institution_profiles: List[str] = []

        # Widget data
        self._widgets: Dict[str, str] = {}

        # Other attributes
        self.unread_messages = 0

        # Flag to prevent recursive login attempts
        self._login_in_progress = False

        # Try to restore session from cache
        self._restore_session()

    def _restore_session(self) -> bool:
        """Attempt to restore session from cache

        Returns:
            bool: True if session was restored
        """
        cached_session = self.session_cache.load_session()
        if not cached_session:
            _LOGGER.debug("No valid cached session found")
            return False

        try:
            # Create a new requests session
            self._session = requests.Session()

            # Restore session data
            self.session_data = AulaSession.model_validate(cached_session)

            # Restore the pickled session if available
            if "_pickled_session" in cached_session:
                try:
                    pickled_data = base64.b64decode(cached_session["_pickled_session"])
                    self._session = pickle.loads(pickled_data)
                    _LOGGER.debug("Restored requests session from cache")
                except Exception as e:
                    _LOGGER.warning(f"Failed to restore pickled session: {e}")

            # Verify the session is still valid
            if self.is_logged_in():
                _LOGGER.info("Successfully restored session from cache")
                return True
            else:
                _LOGGER.debug("Cached session is no longer valid")
                return False
        except Exception as e:
            _LOGGER.warning(f"Failed to restore session: {e}")
            return False

    def _direct_login(self) -> bool:
        """Direct login method that bypasses all checks to prevent recursion

        This method performs the login process without any preconditions or checks
        to prevent infinite recursion. It should only be called from the MCP server's
        login tool.

        Returns:
            bool: True if login was successful
        """
        _LOGGER.debug("Performing direct login to Aula")
        self._session = requests.Session()

        # Initial request to login page
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "da,en-US;q=0.7,en;q=0.3",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        params = {
            "type": "unilogin",
        }

        response = self._session.get(
            LOGIN_URL,
            params=params,
            headers=headers,
            verify=True,
        )

        # Extract form action URL
        _html = BeautifulSoup(response.text, "html.parser")
        try:
            _url = _html.form["action"]
        except (AttributeError, KeyError):
            _LOGGER.error("Could not find login form on Aula login page")
            raise AuthenticationError("Could not find login form")

        # Submit selected IdP form
        headers = {
            "Host": "broker.unilogin.dk",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "da,en-US;q=0.7,en;q=0.3",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "null",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        }

        data = {
            "selectedIdp": "uni_idp",
        }

        response = self._session.post(
            _url,
            headers=headers,
            data=data,
            verify=True,
        )

        # Handle redirect chain with credentials
        user_data = {
            "username": self.config.username,
            "password": self.config.password,
            "selected-aktoer": "KONTAKT",
        }

        redirects = 0
        success = False
        while not success and redirects < 10:
            html = BeautifulSoup(response.text, "html.parser")
            try:
                url = html.form["action"]
            except (AttributeError, KeyError):
                _LOGGER.error(f"Could not find form action after {redirects} redirects")
                break

            post_data = {}
            for input_field in html.find_all("input"):
                if input_field.has_attr("name") and input_field.has_attr("value"):
                    post_data[input_field["name"]] = input_field["value"]

                    # Insert user credentials where needed
                    for key in user_data:
                        if input_field.has_attr("name") and input_field["name"] == key:
                            post_data[key] = user_data[key]

            response = self._session.post(url, data=post_data, verify=True)
            if response.url == "https://www.aula.dk:443/portal/":
                success = True
            redirects += 1

        if not success:
            _LOGGER.error("Failed to log in to Aula after multiple redirects")
            raise AuthenticationError("Login failed after multiple redirects")

        # Find the correct API version
        self._api_url = f"{API_BASE}{API_VERSION}"
        api_ver = int(API_VERSION)
        api_success = False

        while not api_success:
            _LOGGER.debug(f"Trying API at {self._api_url}")
            profiles_response = self._session.get(
                f"{self._api_url}?method=profiles.getProfilesByLogin", verify=True
            )

            if profiles_response.status_code == 410:
                _LOGGER.debug(
                    f"API was expected at {self._api_url} but responded with HTTP 410. "
                    f"Trying a newer version."
                )
                api_ver += 1
            elif profiles_response.status_code == 403:
                msg = "Access to Aula API was denied. Please check credentials."
                _LOGGER.error(msg)
                raise AuthenticationError(msg)
            elif profiles_response.status_code == 200:
                # We found a working API version
                api_success = True
                profiles_data = profiles_response.json()
                self.session_data.profiles = [
                    AulaProfile.model_validate(p)
                    for p in profiles_data["data"]["profiles"]
                ]

            self._api_url = f"{API_BASE}{api_ver}"

        _LOGGER.debug(f"Found API on {self._api_url}")

        # Store CSRF token for API calls
        try:
            self.session_data.csrf_token = self._session.cookies.get_dict()[
                "Csrfp-Token"
            ]
        except KeyError:
            _LOGGER.warning("Could not find CSRF token in cookies")

        # Get profile context
        self._profile_context = self._session.get(
            f"{self._api_url}?method=profiles.getProfileContext&portalrole=guardian",
            verify=True,
        ).json()["data"]["institutionProfile"]["relations"]

        _LOGGER.debug(f"Direct login successful: {success}")

        # Save the session to cache
        if success:
            # Save with the requests session object
            self._save_session()

        return success

    def login(self) -> bool:
        """Log in to Aula and establish a session

        Returns:
            bool: True if login was successful
        """
        # Prevent recursive login calls
        if self._login_in_progress:
            _LOGGER.warning("Login already in progress, avoiding recursion")
            return False

        # Set flag to prevent recursion
        self._login_in_progress = True

        try:
            # First check if we already have a valid session
            if self._session and self.is_logged_in():
                _LOGGER.debug("Already logged in, using existing session")
                return True

            # Call the direct login method
            return self._direct_login()
        finally:
            # Reset flag when done
            self._login_in_progress = False

    def _save_session(self) -> bool:
        """Save current session to cache

        Returns:
            bool: True if successful
        """
        # Create a copy of the session data for serialization
        session_dict = self.session_data.model_dump()

        # Add the pickled session object
        if self._session:
            try:
                pickled_session = pickle.dumps(self._session)
                session_dict["_pickled_session"] = base64.b64encode(
                    pickled_session
                ).decode("utf-8")
            except Exception as e:
                _LOGGER.warning(f"Failed to pickle session: {e}")

        return self.session_cache.save_session(session_dict)

    def is_logged_in(self) -> bool:
        """Check if the client is logged in

        Returns:
            bool: True if logged in
        """
        if not self._session:
            return False

        try:
            response = self._session.get(
                f"{self._api_url}?method=profiles.getProfilesByLogin", verify=True
            ).json()
            return response["status"]["message"] == "OK"
        except Exception as e:
            _LOGGER.debug(f"Failed to check login status: {e}")
            return False

    def get_widgets(self) -> Dict[str, str]:
        """Get available widgets

        Returns:
            Dict[str, str]: Dictionary of widget IDs and names
        """
        widgets_data = self._session.get(
            f"{self._api_url}?method=profiles.getProfileContext", verify=True
        ).json()["data"]["pageConfiguration"]["widgetConfigurations"]

        for widget in widgets_data:
            widget_id = str(widget["widget"]["widgetId"])
            widget_name = widget["widget"]["name"]
            self._widgets[widget_id] = widget_name

        _LOGGER.info(f"Widgets found: {self._widgets}")
        return self._widgets

    def get_token(self, widget_id: str, mock: bool = False) -> str:
        """Get a token for a specific widget

        Args:
            widget_id: The widget ID
            mock: If True, return a mock token

        Returns:
            str: The token
        """
        # Check if we have a cached token
        if widget_id in self.session_data.tokens:
            token_data = self.session_data.tokens[widget_id]
            current_time = datetime.datetime.now(pytz.utc)
            if current_time - token_data.timestamp < datetime.timedelta(minutes=1):
                _LOGGER.debug(f"Reusing existing token for widget {widget_id}")
                return token_data.token

        if mock:
            return "MockToken"

        _LOGGER.debug(f"Requesting new token for widget {widget_id}")
        bearer_token = self._session.get(
            f"{self._api_url}?method=aulaToken.getAulaToken&widgetId={widget_id}",
            verify=True,
        ).json()["data"]

        token = f"Bearer {bearer_token}"
        self.session_data.tokens[widget_id] = AulaToken(
            token=token, timestamp=datetime.datetime.now(pytz.utc)
        )

        # Save updated token to cache
        self._save_session()

        return token

    def api_call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        post_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        """Make an API call to Aula

        Args:
            method: The API method to call
            params: Optional query parameters
            post_data: Optional data to send in POST request
            max_retries: Maximum number of retry attempts if auth fails

        Returns:
            Dict[str, Any]: The API response
        """
        # Make sure we're logged in, but avoid recursive login attempts
        if not self._login_in_progress and not self.is_logged_in():
            _LOGGER.debug("Not logged in, attempting login before API call")
            login_success = self.login()
            if not login_success:
                return {"status": {"message": "ERROR", "code": 401}, "data": None}

        url = f"{self._api_url}?method={method}"

        # Add any additional query parameters
        if params:
            for key, value in params.items():
                url += f"&{key}={value}"

        headers = {
            "csrfp-token": self.session_data.csrf_token,
            "content-type": "application/json",
        }

        retries = 0
        while retries <= max_retries:
            try:
                if post_data:
                    _LOGGER.debug(f"Making POST API call to {url}")
                    response = self._session.post(
                        url, headers=headers, json=post_data, verify=True
                    )
                else:
                    _LOGGER.debug(f"Making GET API call to {url}")
                    response = self._session.get(url, headers=headers, verify=True)

                # Check for authentication failures
                if response.status_code == 403:
                    if retries < max_retries:
                        _LOGGER.warning("Authentication failed, attempting to re-login")
                        # Clear session and try to login again without recursion
                        self.session_cache.clear_cache()
                        self._session = None
                        # Only try to login if we're not already in a login process
                        if not self._login_in_progress:
                            self.login()
                        retries += 1
                        continue
                    else:
                        _LOGGER.error("API call failed after max retries")
                        return {
                            "status": {"message": "ERROR", "code": 403},
                            "data": None,
                        }

                result = response.json()
                # Check for expired session in the API response
                if result.get("status", {}).get("code") == 403:
                    if retries < max_retries:
                        _LOGGER.warning("Session expired, attempting to re-login")
                        # Clear session and try to login again
                        self.session_cache.clear_cache()
                        self._session = None
                        # Only try to login if we're not already in a login process
                        if not self._login_in_progress:
                            self.login()
                        retries += 1
                        continue

                return result
            except json.JSONDecodeError:
                _LOGGER.error(f"Failed to decode API response as JSON: {response.text}")
                return {"status": {"message": "ERROR", "code": 500}, "data": None}
            except Exception as e:
                if retries < max_retries:
                    _LOGGER.warning(f"API call failed: {e}, retrying...")
                    retries += 1
                    continue
                _LOGGER.error(f"API call failed after {retries} retries: {e}")
                return {"status": {"message": "ERROR", "code": 500}, "data": None}

        # This should never be reached, but just in case
        return {"status": {"message": "ERROR", "code": 500}, "data": None}
