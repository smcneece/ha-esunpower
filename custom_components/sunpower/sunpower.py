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

    def __init__(self, host):
        """Initialize."""
        self.host = host
        self.command_url = "http://{0}/cgi-bin/dl_cgi?Command=".format(host)

    async def generic_command_async(self, command):
        """All 'commands' to the PVS module use this url pattern and return json
        The PVS system can take a very long time to respond so timeout is at 2 minutes"""
        url = self.command_url + command
        timeout = aiohttp.ClientTimeout(total=120)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    text = await response.text()
                    return simplejson.loads(text)
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
        """Get the status of the energy storage system - ASYNC"""
        url = "http://{0}/cgi-bin/dl_cgi/energy-storage-system/status".format(self.host)
        timeout = aiohttp.ClientTimeout(total=120)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
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