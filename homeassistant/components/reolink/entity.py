"""Reolink parent entity class."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reolink_aio.api import DUAL_LENS_MODELS, Host

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import ReolinkData
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class ReolinkChannelEntityDescription(EntityDescription):
    """A class that describes entities for a camera channel."""

    cmd_key: str | None = None
    supported: Callable[[Host, int], bool] = lambda api, ch: True


@dataclass(frozen=True, kw_only=True)
class ReolinkHostEntityDescription(EntityDescription):
    """A class that describes host entities."""

    cmd_key: str | None = None
    supported: Callable[[Host], bool] = lambda api: True


class ReolinkBaseCoordinatorEntity[_DataT](
    CoordinatorEntity[DataUpdateCoordinator[_DataT]]
):
    """Parent class for Reolink entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        reolink_data: ReolinkData,
        coordinator: DataUpdateCoordinator[_DataT],
    ) -> None:
        """Initialize ReolinkBaseCoordinatorEntity."""
        super().__init__(coordinator)

        self._host = reolink_data.host

        http_s = "https" if self._host.api.use_https else "http"
        self._conf_url = f"{http_s}://{self._host.api.host}:{self._host.api.port}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._host.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, self._host.api.mac_address)},
            name=self._host.api.nvr_name,
            model=self._host.api.model,
            manufacturer=self._host.api.manufacturer,
            hw_version=self._host.api.hardware_version,
            sw_version=self._host.api.sw_version,
            serial_number=self._host.api.uid,
            configuration_url=self._conf_url,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._host.api.session_active and super().available


class ReolinkHostCoordinatorEntity(ReolinkBaseCoordinatorEntity[None]):
    """Parent class for entities that control the Reolink NVR itself, without a channel.

    A camera connected directly to HomeAssistant without using a NVR is in the reolink API
    basically a NVR with a single channel that has the camera connected to that channel.
    """

    entity_description: ReolinkHostEntityDescription | ReolinkChannelEntityDescription

    def __init__(self, reolink_data: ReolinkData) -> None:
        """Initialize ReolinkHostCoordinatorEntity."""
        super().__init__(reolink_data, reolink_data.device_coordinator)

        self._attr_unique_id = f"{self._host.unique_id}_{self.entity_description.key}"

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        cmd_key = self.entity_description.cmd_key
        if cmd_key is not None:
            self._host.async_register_update_cmd(cmd_key)

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        cmd_key = self.entity_description.cmd_key
        if cmd_key is not None:
            self._host.async_unregister_update_cmd(cmd_key)

        await super().async_will_remove_from_hass()


class ReolinkChannelCoordinatorEntity(ReolinkHostCoordinatorEntity):
    """Parent class for Reolink hardware camera entities connected to a channel of the NVR."""

    entity_description: ReolinkChannelEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
    ) -> None:
        """Initialize ReolinkChannelCoordinatorEntity for a hardware camera connected to a channel of the NVR."""
        super().__init__(reolink_data)

        self._channel = channel
        self._attr_unique_id = (
            f"{self._host.unique_id}_{channel}_{self.entity_description.key}"
        )

        dev_ch = channel
        if self._host.api.model in DUAL_LENS_MODELS:
            dev_ch = 0

        if self._host.api.is_nvr:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{self._host.unique_id}_ch{dev_ch}")},
                via_device=(DOMAIN, self._host.unique_id),
                name=self._host.api.camera_name(dev_ch),
                model=self._host.api.camera_model(dev_ch),
                manufacturer=self._host.api.manufacturer,
                sw_version=self._host.api.camera_sw_version(dev_ch),
                configuration_url=self._conf_url,
            )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        cmd_key = self.entity_description.cmd_key
        if cmd_key is not None:
            self._host.async_register_update_cmd(cmd_key, self._channel)

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        cmd_key = self.entity_description.cmd_key
        if cmd_key is not None:
            self._host.async_unregister_update_cmd(cmd_key, self._channel)

        await super().async_will_remove_from_hass()
