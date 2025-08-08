# Advanced configuration schema - cleaner without sun elevation
        schema = vol.Schema({
            vol.Required("general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("deep_debug_notifications", default=False): selector.BooleanSelector(),
            vol.Required("overwrite_general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("mobile_notifications", default=False): selector.BooleanSelector(),
            vol.Optional("mobile_device", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in mobile_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("route_check_enabled", default=False): selector.BooleanSelector(),
            vol.Optional("route_gateway_ip", default="192.168.1.80"): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                )
            ),
        })