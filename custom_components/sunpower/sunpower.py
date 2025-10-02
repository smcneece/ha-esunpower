""" Basic Sunpower PVS Tool - ASYNC VERSION - Enhanced with Varserver Support """

import aiohttp
import asyncio
import simplejson
import logging

_LOGGER = logging.getLogger(__name__)

PVS_AUTH_USERNAME = "ssm_owner"


class ConnectionException(Exception):
    """Any failure to connect to sunpower PVS"""


class ParseException(Exception):
    """Any failure to connect to sunpower PVS"""


class VarserverError(Exception):
    """Varserver operation failed"""


class SunPowerMonitor:
    """Basic Class to talk to sunpower pvs 5/6 via the management interface 'API'.
    This is not a public API so it might fail at any time.
    if you find this useful please complain to sunpower and your sunpower dealer that they
    do not have a public API

    Enhanced for firmware 61839+ with cookie-based session authentication and varserver support"""

    def __init__(self, host, auth_password=None):
        """Initialize SunPower PVS monitor.

        Args:
            host: PVS IP address (e.g., '172.27.153.1')
            auth_password: PVS serial last 5 characters for firmware 61839+ authentication
        """
        self.host = host
        self.auth_password = auth_password
        self.command_url = "http://{0}/cgi-bin/dl_cgi?Command=".format(host)
        self._session = None
        self._authenticated = False
        self._auth_header = None

        if auth_password:
            # Generate Basic Auth header for ssm_owner:password
            # Use lowercase "basic" per pypvs standard
            import base64
            auth_string = f"{PVS_AUTH_USERNAME}:{auth_password}"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
            self._auth_header = f"basic {auth_b64}"

    async def _ensure_session(self):
        """Ensure we have an active aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._authenticated = False

    async def _authenticate_session(self):
        """Authenticate the session using /auth?login endpoint for cookie-based auth

        This matches SunStrong's pypvs approach:
        1. GET https://{host}/auth?login with Basic Auth header
        2. PVS returns 200 OK with session cookie
        3. Subsequent requests use the cookie automatically
        """
        if not self._auth_header:
            return False

        await self._ensure_session()

        try:
            # Clear cookies before authentication (pypvs PR#7 fix)
            # Cookies seem to be added implicitly, so need to clear them for clean auth
            # https://docs.aiohttp.org/en/stable/client_advanced.html#cookie-jar
            self._session.cookie_jar.clear()

            # Use HTTPS for authentication endpoint (per SunStrong/pypvs)
            auth_url = f"https://{self.host}/auth?login"
            headers = {"Authorization": self._auth_header}

            _LOGGER.debug("Attempting authentication to %s", auth_url)

            async with self._session.get(auth_url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    # Session cookie should now be stored in session
                    self._authenticated = True
                    _LOGGER.info("Cookie-based authentication successful")
                    return True
                else:
                    response_text = await response.text()
                    _LOGGER.warning("Authentication failed: HTTP %d, Response: %s",
                                   response.status, response_text[:200])
                    return False
        except Exception as e:
            _LOGGER.error("Authentication session error: %s", e)
            return False

    async def _logout_session(self):
        """Logout from authenticated session"""
        if self._session and not self._session.closed and self._authenticated:
            try:
                logout_url = f"https://{self.host}/auth?logout"
                async with self._session.get(logout_url, ssl=False):
                    pass  # Don't care about response
            except Exception:
                pass  # Ignore logout errors
            finally:
                self._authenticated = False

    async def close(self):
        """Clean up session resources"""
        await self._logout_session()
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def generic_command_async(self, command):
        """All 'commands' to the PVS module use this url pattern and return json
        The PVS system can take a very long time to respond so timeout is at 2 minutes

        Enhanced authentication flow (matches SunStrong/pypvs):
        1. Try unauthenticated request first (legacy firmware compatibility)
        2. If 401/403, authenticate via /auth?login to get session cookie
        3. Retry request with cookie-authenticated session
        4. Handle cookie expiration with re-authentication
        """
        url = self.command_url + command
        await self._ensure_session()

        try:
            # First attempt: unauthenticated (works with old firmware)
            async with self._session.get(url) as response:
                if response.status == 200:
                    # Success without authentication - old firmware
                    text = await response.text()
                    return simplejson.loads(text)
                elif response.status in [401, 403]:
                    # Authentication required (new firmware 61839+)
                    if self._auth_header:
                        # Authenticate session to get cookie
                        if await self._authenticate_session():
                            # Retry with authenticated session (cookie stored automatically)
                            async with self._session.get(url) as auth_response:
                                if auth_response.status == 200:
                                    text = await auth_response.text()
                                    return simplejson.loads(text)
                                elif auth_response.status in [401, 403]:
                                    # Cookie may have expired, try re-authentication once
                                    self._authenticated = False
                                    if await self._authenticate_session():
                                        async with self._session.get(url) as retry_response:
                                            if retry_response.status == 200:
                                                text = await retry_response.text()
                                                return simplejson.loads(text)
                                            else:
                                                raise ConnectionException(f"Authentication failed after retry: HTTP {retry_response.status}")
                                    else:
                                        raise ConnectionException("Session re-authentication failed")
                                else:
                                    raise ConnectionException(f"Authenticated request failed: HTTP {auth_response.status}")
                        else:
                            raise ConnectionException("Initial authentication failed - check PVS serial number")
                    else:
                        raise ConnectionException("Authentication required but no PVS serial provided")
                else:
                    # Other HTTP errors (500, 404, 400, etc.)
                    raise ConnectionException(f"PVS returned HTTP {response.status}")

        except aiohttp.ClientError as error:
            raise ConnectionException from error
        except simplejson.errors.JSONDecodeError as error:
            raise ParseException from error
        except asyncio.TimeoutError as error:
            raise ConnectionException from error

    async def device_list_async(self):
        """Get a list of all devices connected to the PVS - ASYNC"""
        return await self.generic_command_async("DeviceList")

    async def energy_storage_system_status_async(self):
        """Get the status of the energy storage system - ASYNC

        Uses cookie-based authentication for new firmware
        """
        url = "http://{0}/cgi-bin/dl_cgi/energy-storage-system/status".format(self.host)
        await self._ensure_session()

        try:
            # First attempt: unauthenticated
            async with self._session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    return simplejson.loads(text)
                elif response.status in [401, 403]:
                    # Authentication required
                    if self._auth_header:
                        # Authenticate session
                        if await self._authenticate_session():
                            # Retry with authenticated session
                            async with self._session.get(url) as auth_response:
                                if auth_response.status == 200:
                                    text = await auth_response.text()
                                    return simplejson.loads(text)
                                else:
                                    raise ConnectionException(f"ESS endpoint returned HTTP {auth_response.status}")
                        else:
                            raise ConnectionException("Authentication failed for ESS endpoint - check PVS serial number")
                    else:
                        raise ConnectionException("Authentication required for ESS endpoint but no PVS serial provided")
                else:
                    raise ConnectionException(f"ESS endpoint returned HTTP {response.status}")
        except aiohttp.ClientError as error:
            raise ConnectionException from error
        except simplejson.errors.JSONDecodeError as error:
            raise ParseException from error
        except asyncio.TimeoutError as error:
            raise ConnectionException from error

    async def network_status_async(self):
        """Get a list of network interfaces on the PVS - ASYNC"""
        return await self.generic_command_async("Get_Comm")
