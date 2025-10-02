""" Basic Sunpower PVS Tool - ASYNC VERSION - Enhanced with Varserver Support """

import aiohttp
import asyncio
import simplejson
import logging

from .const import PVS_AUTH_USERNAME

from .varserver import VarserverClient, VarserverError

# Future: Switch to bundled pypvs when ready
# from .pypvs_bundle.pvs import PVS
# from .pypvs_bundle.updaters.ess import PVSESSUpdater
# from .pypvs_bundle.models.pvs import PVSData
# from .pypvs_bundle.exceptions import ENDPOINT_PROBE_EXCEPTIONS
USE_FULL_PYPVS = False  # Set to True when pypvs bundle is ready

_LOGGER = logging.getLogger(__name__)


class ConnectionException(Exception):
    """Any failure to connect to sunpower PVS"""


class ParseException(Exception):
    """Any failure to connect to sunpower PVS"""


class SunPowerMonitor:
    """Basic Class to talk to sunpower pvs 5/6 via the management interface 'API'.
    This is not a public API so it might fail at any time.
    if you find this useful please complain to sunpower and your sunpower dealer that they
    do not have a public API"""

    def __init__(self, host, auth_password=None):
        """Initialize SunPower PVS monitor.

        Args:
            host: PVS IP address (e.g., '172.27.153.1')
            auth_password: Optional PVS serial last 5 characters for firmware 61840+ authentication
        """
        self.host = host
        self.auth_password = auth_password
        self.command_url = "http://{0}/cgi-bin/dl_cgi?Command=".format(host)
        self._session = None
        self._authenticated = False
        self._auth_header = None
        self._varserver_available = None
        self._varserver_client = None

        if auth_password:
            # Generate Basic Auth header for username:password
            # Use lowercase "basic" per pypvs standard
            import base64
            auth_string = f"{PVS_AUTH_USERNAME}:{auth_password}"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
            self._auth_header = f"basic {auth_b64}"
            _LOGGER.info("Authentication configured - username: %s, serial: ***%s (last 2 shown)",
                        PVS_AUTH_USERNAME, auth_password[-2:] if len(auth_password) >= 2 else "??")

    async def _ensure_session(self):
        """Ensure we have an active aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._authenticated = False

    async def _authenticate_session(self):
        """Authenticate the session using login endpoint for token-based auth
        Per LocalAPI.md: GET to /auth?login with Basic auth to get session cookie
        """
        if not self._auth_header:
            return False

        await self._ensure_session()

        try:
            # Clear cookies before authentication (pypvs PR#7 fix)
            # Cookies seem to be added implicitly, so need to clear them for clean auth
            # https://docs.aiohttp.org/en/stable/client_advanced.html#cookie-jar
            self._session.cookie_jar.clear()

            # Use HTTPS for authentication endpoint per LocalAPI.md
            auth_url = f"https://{self.host}/auth?login"
            headers = {"Authorization": self._auth_header}

            async with self._session.get(auth_url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    # Session cookie should now be stored in session
                    self._authenticated = True
                    return True
                else:
                    response_text = await response.text()
                    _LOGGER.warning("Authentication failed: HTTP %d %s, Response: %s",
                                   response.status, response.reason, response_text[:200])
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
        if self._varserver_client:
            await self._varserver_client.close()
            self._varserver_client = None

    def get_varserver_status(self):
        """Get status of varserver capability

        Returns dict with capability info for diagnostics
        """
        return {
            "varserver_detected": self._varserver_available,
            "auth_configured": bool(self.auth_password),
            "recommendation": self._get_varserver_recommendation()
        }

    def _get_varserver_recommendation(self):
        """Get recommendation for user based on current state"""
        if not self.auth_password:
            return "For firmware 61840+ support, configure PVS serial in integration settings"
        elif self._varserver_available is False:
            return "PVS firmware does not support varserver (older than 61840)"
        elif self._varserver_available is True:
            return "Varserver capability active - using modern endpoints"
        else:
            return "Varserver capability not yet tested"

    async def detect_varserver_capability(self):
        """Detect if the PVS supports varserver (FCGI) endpoints

        Returns True if varserver is available, False for legacy dl_cgi only
        """

        if self._varserver_available is not None:
            return self._varserver_available

        if not self.auth_password:
            _LOGGER.debug("No auth password provided, assuming legacy firmware")
            self._varserver_available = False
            return False

        try:
            # Create varserver client and test capability
            self._varserver_client = VarserverClient(
                host=self.host,
                username=PVS_AUTH_USERNAME,
                password=self.auth_password
            )

            # Test varserver availability
            varserver_responsive = await self._varserver_client.probe_capability()

            if varserver_responsive:
                self._varserver_available = True
                _LOGGER.info("Varserver capability detected on PVS %s", self.host)
                return True
            else:
                self._varserver_available = False
                await self._varserver_client.close()
                self._varserver_client = None
                return False

        except VarserverError as e:
            _LOGGER.debug("Varserver probe failed: %s, falling back to dl_cgi", e)
            self._varserver_available = False
            if self._varserver_client:
                await self._varserver_client.close()
                self._varserver_client = None
            return False
        except Exception as e:
            _LOGGER.warning("Unexpected error during varserver detection: %s, using dl_cgi", e)
            self._varserver_available = False
            if self._varserver_client:
                await self._varserver_client.close()
                self._varserver_client = None
            return False

    async def generic_command_async(self, command):
        """All 'commands' to the PVS module use this url pattern and return json
        The PVS system can take a very long time to respond so timeout is at 2 minutes

        Enhanced authentication flow:
        1. Try unauthenticated request first (legacy compatibility)
        2. If 401/403, authenticate session and retry using cookies
        3. If session expires, re-authenticate automatically
        """
        url = self.command_url + command
        await self._ensure_session()

        try:
            # First attempt: unauthenticated (works with current firmware)
            async with self._session.get(url) as response:
                if response.status == 200:
                    # Success without authentication - current firmware
                    text = await response.text()
                    return simplejson.loads(text)
                elif response.status in [401, 403]:
                    # Authentication required (new firmware) - try session-based auth
                    if self._auth_header:
                        # Authenticate session to get cookie
                        if await self._authenticate_session():
                            # Retry with authenticated session (uses stored cookie)
                            async with self._session.get(url) as auth_response:
                                if auth_response.status == 200:
                                    text = await auth_response.text()
                                    return simplejson.loads(text)
                                elif auth_response.status in [401, 403]:
                                    # Session may have expired, try to re-authenticate once
                                    self._authenticated = False
                                    if await self._authenticate_session():
                                        async with self._session.get(url) as retry_response:
                                            if retry_response.status == 200:
                                                text = await retry_response.text()
                                                return simplejson.loads(text)
                                            else:
                                                response_text = await retry_response.text()
                                                _LOGGER.error("Authentication failed after retry: HTTP %d %s, Response: %s",
                                                             retry_response.status, retry_response.reason, response_text[:500])
                                                raise ConnectionException(f"Authentication failed after retry: HTTP {retry_response.status}")
                                    else:
                                        raise ConnectionException("Session re-authentication failed")
                                else:
                                    response_text = await auth_response.text()
                                    _LOGGER.error("Authenticated request failed: HTTP %d %s, Response: %s",
                                                 auth_response.status, auth_response.reason, response_text[:500])
                                    raise ConnectionException(f"Authenticated request failed: HTTP {auth_response.status}")
                        else:
                            raise ConnectionException("Initial authentication failed - check PVS serial number")
                    else:
                        raise ConnectionException("Authentication required but no PVS serial provided")
                else:
                    # Other HTTP errors (500, 404, etc.) - don't try authentication
                    response_text = await response.text()
                    _LOGGER.error("PVS request failed: HTTP %d %s, Response: %s",
                                 response.status, response.reason, response_text[:500])
                    raise ConnectionException(f"PVS request failed: HTTP {response.status} {response.reason}")

        except aiohttp.ClientError as error:
            _LOGGER.error("HTTP client error during PVS request: %s", error)
            raise ConnectionException from error
        except simplejson.errors.JSONDecodeError as error:
            _LOGGER.error("JSON parsing error - invalid response from PVS: %s", error)
            raise ParseException from error
        except asyncio.TimeoutError as error:
            _LOGGER.error("Request timeout - PVS took longer than 120 seconds to respond")
            raise ConnectionException from error

    def generic_command(self, command):
        """DEPRECATED: Sync wrapper for backward compatibility
        WARNING: This may cause issues in async environments like Home Assistant.
        Use generic_command_async() instead."""
        import warnings
        warnings.warn(
            "generic_command() is deprecated. Use generic_command_async() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Try to run in existing event loop if possible
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(self.generic_command_async(command))
        else:
            # Already in a loop, we can't use asyncio.run()
            # This should not happen in proper async code
            raise RuntimeError(
                "Cannot use sync method from within async context. "
                "Use generic_command_async() instead."
            )

    async def device_list_async(self):
        """Get a list of all devices connected to the PVS - ASYNC

        Enhanced to try varserver first (required for firmware 61840+), fallback to dl_cgi
        """
        # Try varserver if available (new firmware requires this)
        if await self.detect_varserver_capability():
            try:
                return await self._get_device_list_varserver()
            except Exception as e:
                _LOGGER.warning("Varserver DeviceList failed, falling back to dl_cgi: %s", e)

        # Fallback to legacy dl_cgi endpoint (old firmware)
        return await self.generic_command_async("DeviceList")

    async def _get_device_list_varserver(self):
        """Get DeviceList using varserver (required for firmware 61840+)"""
        if not self._varserver_client:
            raise ConnectionException("Varserver not properly initialized")

        try:
            device_list = await self._varserver_client.fetch_device_list()
            _LOGGER.info("Successfully fetched DeviceList via varserver (%d devices)", len(device_list.get("devices", [])))
            return device_list

        except VarserverError as e:
            _LOGGER.error("Failed to get DeviceList from varserver: %s", e)
            raise ConnectionException(f"Varserver DeviceList failed: {e}")

    def device_list(self):
        """DEPRECATED: Get a list of all devices connected to the PVS - SYNC WRAPPER
        WARNING: This may cause issues in async environments like Home Assistant.
        Use device_list_async() instead."""
        import warnings
        warnings.warn(
            "device_list() is deprecated. Use device_list_async() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Try to run in existing event loop if possible
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(self.device_list_async())
        else:
            # Already in a loop, we can't use asyncio.run()
            # This should not happen in proper async code
            raise RuntimeError(
                "Cannot use sync method from within async context. "
                "Use device_list_async() instead."
            )

    async def energy_storage_system_status_async(self):
        """Get the status of the energy storage system - ASYNC

        Enhanced to try varserver first, fallback to legacy dl_cgi endpoint
        """
        # Try varserver if available
        if await self.detect_varserver_capability():
            try:
                return await self._get_ess_data_varserver()
            except Exception as e:
                _LOGGER.warning("Varserver ESS data failed, falling back to dl_cgi: %s", e)

        # Fallback to legacy dl_cgi endpoint
        return await self._get_ess_data_legacy()

    async def _get_ess_data_varserver(self):
        """Get ESS data using varserver (modern, efficient approach)"""
        if not self._varserver_client:
            raise ConnectionException("Varserver not properly initialized")

        try:
            # Fetch ESS data efficiently (all variables in one request)
            ess_grouped = await self._varserver_client.fetch_ess_data()

            # Convert to legacy format for backward compatibility
            legacy_format = self._varserver_client.convert_ess_to_legacy_format(ess_grouped)

            _LOGGER.debug("Successfully fetched ESS data via varserver")
            return legacy_format

        except VarserverError as e:
            _LOGGER.error("Failed to get ESS data from varserver: %s", e)
            raise ConnectionException(f"Varserver ESS data failed: {e}")

    async def _get_ess_data_legacy(self):
        """Get ESS data using legacy dl_cgi endpoint"""
        url = "http://{0}/cgi-bin/dl_cgi/energy-storage-system/status".format(self.host)
        timeout = aiohttp.ClientTimeout(total=120)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # First attempt: unauthenticated
                async with session.get(url) as response:
                    if response.status in [401, 403]:
                        # Authentication required
                        if self._auth_header:
                            # Retry with authentication
                            headers = {"Authorization": self._auth_header}
                            async with session.get(url, headers=headers) as auth_response:
                                if auth_response.status in [401, 403]:
                                    response_text = await auth_response.text()
                                    _LOGGER.error("ESS authentication failed: HTTP %d %s, Response: %s",
                                                 auth_response.status, auth_response.reason, response_text[:200])
                                    raise ConnectionException("Authentication failed for ESS endpoint - check PVS serial number")
                                text = await auth_response.text()
                                return simplejson.loads(text)
                        else:
                            raise ConnectionException("Authentication required for ESS endpoint but no PVS serial provided")
                    else:
                        # Success without authentication
                        text = await response.text()
                        return simplejson.loads(text)
        except aiohttp.ClientError as error:
            raise ConnectionException from error
        except simplejson.errors.JSONDecodeError as error:
            raise ParseException from error
        except asyncio.TimeoutError as error:
            raise ConnectionException from error

    def energy_storage_system_status(self):
        """DEPRECATED: Get the status of the energy storage system - SYNC WRAPPER
        WARNING: This may cause issues in async environments like Home Assistant.
        Use energy_storage_system_status_async() instead."""
        import warnings
        warnings.warn(
            "energy_storage_system_status() is deprecated. Use energy_storage_system_status_async() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Try to run in existing event loop if possible
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(self.energy_storage_system_status_async())
        else:
            # Already in a loop, we can't use asyncio.run()
            # This should not happen in proper async code
            raise RuntimeError(
                "Cannot use sync method from within async context. "
                "Use energy_storage_system_status_async() instead."
            )

    async def network_status_async(self):
        """Get a list of network interfaces on the PVS - ASYNC"""
        return await self.generic_command_async("Get_Comm")

    def network_status(self):
        """DEPRECATED: Get a list of network interfaces on the PVS - SYNC WRAPPER
        WARNING: This may cause issues in async environments like Home Assistant.
        Use network_status_async() instead."""
        import warnings
        warnings.warn(
            "network_status() is deprecated. Use network_status_async() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Try to run in existing event loop if possible
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(self.network_status_async())
        else:
            # Already in a loop, we can't use asyncio.run()
            # This should not happen in proper async code
            raise RuntimeError(
                "Cannot use sync method from within async context. "
                "Use network_status_async() instead."
            )