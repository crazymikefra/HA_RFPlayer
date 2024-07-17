"""Support for Rfplayer sensors."""
import logging

from homeassistant.const import (
    CONF_DEVICES,CONF_DEVICES)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import (async_dispatcher_connect)

from . import DATA_DEVICE_REGISTER, EVENT_KEY_SENSOR, RfplayerDevice
from .const import (
    CONF_AUTOMATIC_ADD,
    DATA_DEVICE_REGISTER,
    DATA_ENTITY_LOOKUP,
    DOMAIN,
    EVENT_KEY_ID,
    EVENT_KEY_SENSOR,
    EVENT_KEY_UNIT,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_ICONS = {
    "humidity": "mdi:water-percent",
    "battery": "mdi:battery",
    "temperature": "mdi:thermometer",
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Rfplayer platform."""

    config = entry.data
    options = entry.options
    #_LOGGER.debug("config : %s",str(config))
    #_LOGGER.debug("options : %s",str(options))

    # add jamming entity
    #async_add_entities([RfplayerJammingSensor()])

    async def add_new_device(device_info):
        _LOGGER.debug("Add sensor entity %s", device_info)
        """Check if device is known, otherwise create device entity."""
        device_id = device_info[EVENT_KEY_ID]
        # create entity
        device = RfplayerSensor(
            protocol=device_id.split("_")[0],
            device_id=device_id.split("_")[1],
            unit_of_measurement=device_info[EVENT_KEY_UNIT],
            initial_event=device_info,
        )
        
        async_add_entities([device])
        
    if CONF_DEVICES in config:
        items_to_delete=[]
        for device_id, device_info in config[CONF_DEVICES].items():
            if EVENT_KEY_SENSOR in device_info:
                if((device_info.get("protocol")!=None) and (device_info.get("platform")=="sensor") and (device_info.get("platform")=="sensor")):
                    await add_new_device(device_info)
                else :
                    _LOGGER.warning("Sensor entity not created %s - %s", device_id, device_info)
                    items_to_delete.append(device_id)

        for item in items_to_delete:
            config[CONF_DEVICES].pop(item)
    
                

    if options.get(CONF_AUTOMATIC_ADD, config[CONF_AUTOMATIC_ADD]):
        hass.data[DOMAIN][DATA_DEVICE_REGISTER][EVENT_KEY_SENSOR] = add_new_device

async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
    _LOGGER.debug("Removing %s",str(entry))
    """Handle removal of an entry."""

class RfplayerSensor(RfplayerDevice):
    """Representation of a Rfplayer sensor."""

    def __init__(
        self,
        protocol,
        device_id=None,
        unit_of_measurement=None,
        initial_event=None,
        name=None,
        **kwargs,
    ):
        """Handle sensor specific args and super init."""
        self._protocol = protocol
        self._device_id = device_id
        self._attr_name = name
        self._attr_unit_of_measurement = unit_of_measurement


        if(("sysstatus" in protocol)or("SYSSTATUS" in protocol)):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        _LOGGER.info("RfPlayer Sensor ID : %s",device_id)
        #else:
        #    _LOGGER.info("Check ID : %s",device_id)
        
        super().__init__(
            protocol, device_id=device_id, initial_event=initial_event, name=name
        )

    async def async_added_to_hass(self):
        """Register update callback."""
        # Register id and aliases
        await super().async_added_to_hass()

        _LOGGER.debug("async_added_to_hass : _event=%s",self._event)

        if self._event is None:
            old_state = await self.async_get_last_state()
            _LOGGER.debug("async_added_to_hass : old_state=%s",old_state)
            if old_state is not None:
                self._state = old_state.state
                self.schedule_update_ha_state()
                """
                async_dispatcher_connect(
                    self._hass, DATA_UPDATED, self._schedule_immediate_update
                )
                """
            else:
                if self._initial_event:
                    self.hass.data[DOMAIN][DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR][
                        self._initial_event[EVENT_KEY_ID]
                    ] = self.entity_id

    async def async_will_remove_from_hass(self):
        #await super().async_will_remove_from_hass()
        async def async_will_remove_from_hass(self):
            """Clean up after entity before removal."""
            _LOGGER.info("async_will_remove_from_hass ")
            self._data.clear_session()

    async def async_unload_entry(hass, entry):
        """Unload a config entry."""
        _LOGGER.debug("Unloading %s",str(entry))
        await hass.config_entries.async_unload_platforms(entry, "sensor")
        return True
        

    async def async_remove_entry(hass, entry) -> None:
        """Handle removal of an entry."""
        _LOGGER.debug("Removing %s",str(entry))
        try:
            await hass.config_entries.async_forward_entry_unload(entry, "sensor")
            _LOGGER.info("Successfully removed sensor from the integration")
        except ValueError:
            pass

    async def async_remove_config_entry_device(
        hass, config_entry, device_entry
    ) -> bool:
        return True
        """Remove a config entry from a device."""

    def _handle_event(self, event):
        """Domain specific event handler."""
        self._state = event["value"]

    @property
    def state(self):
        """Return value."""
        return self._state

