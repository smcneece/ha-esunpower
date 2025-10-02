""" Basic Sunpower PVS Tool - ASYNC VERSION - FIXED """

import aiohttp
import asyncio
import simplejson


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
        """Initialize."""
        self.host = host
        self.auth_password = auth_password
        self.command_url = "http://{0}/cgi-bin/dl_cgi?Command=".format(host)
        self._auth_header = None
        if auth_password:
            # Generate Basic Auth header for ssm_owner:password
            import base64
            auth_string = f"ssm_owner:{auth_password}"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
            self._auth_header = f"basic {auth_b64}"

    async def generic_command_async(self, command):
        """All 'commands' to the PVS module use this url pattern and return json
        The PVS system can take a very long time to respond so timeout is at 2 minutes

        Handles authentication fallback:
        1. Try unauthenticated request first
        2. If 401/403, retry with authentication (if password available)
        """
        url = self.command_url + command
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
                                    raise ConnectionException("Authentication failed - check PVS serial number")
                                elif auth_response.status == 200:
                                    text = await auth_response.text()
                                    return simplejson.loads(text)
                                else:
                                    raise ConnectionException(f"PVS returned HTTP {auth_response.status}")
                        else:
                            raise ConnectionException("Authentication required but no PVS serial provided")
                    elif response.status == 200:
                        # Success without authentication
                        text = await response.text()
                        return simplejson.loads(text)
                    else:
                        # Other HTTP error
                        raise ConnectionException(f"PVS returned HTTP {response.status}")
        except aiohttp.ClientError as error:
            raise ConnectionException from error
        except simplejson.errors.JSONDecodeError as error:
            raise ParseException from error
        except asyncio.TimeoutError as error:
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
        """Get a list of all devices connected to the PVS - ASYNC"""
        return await self.generic_command_async("DeviceList")

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

        Note: This uses a different URL format than generic_command_async,
        so we need custom authentication handling here.
        """
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
                                    raise ConnectionException("Authentication failed for ESS endpoint - check PVS serial number")
                                elif auth_response.status == 200:
                                    text = await auth_response.text()
                                    return simplejson.loads(text)
                                else:
                                    raise ConnectionException(f"PVS ESS endpoint returned HTTP {auth_response.status}")
                        else:
                            raise ConnectionException("Authentication required for ESS endpoint but no PVS serial provided")
                    elif response.status == 200:
                        # Success without authentication
                        text = await response.text()
                        return simplejson.loads(text)
                    else:
                        # Other HTTP error
                        raise ConnectionException(f"PVS ESS endpoint returned HTTP {response.status}")
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