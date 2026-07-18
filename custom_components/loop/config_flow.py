"""Config flow for the Loop integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_NAME, CONF_WEBHOOK_ID, DOMAIN


class LoopConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an AID app instance (Loop, Trio, …).

    Each instance gets its own webhook and config entry, so several apps can
    push side by side.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._webhook_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Generate a webhook, ask for an instance name, show the URL to paste."""
        if user_input is not None and self._webhook_id is not None:
            await self.async_set_unique_id(self._webhook_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or "Loop",
                data={CONF_WEBHOOK_ID: self._webhook_id},
            )

        self._webhook_id = webhook.async_generate_id()
        try:
            base_url = get_url(self.hass, allow_internal=True, prefer_external=True)
        except NoURLAvailableError:
            base_url = "http://<your-home-assistant>:8123"
        webhook_url = f"{base_url}{webhook.async_generate_path(self._webhook_id)}"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_NAME, default="Loop"): str}),
            description_placeholders={"webhook_url": webhook_url},
        )
