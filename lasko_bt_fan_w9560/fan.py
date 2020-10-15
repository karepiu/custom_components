"""
Adds support for the Lasko BT Fan W9560.
"""
import logging
from datetime import timedelta

from typing import Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .laskofan import LaskoFanDevice

from homeassistant.components.fan import (
    SUPPORT_SET_SPEED,
    SUPPORT_DIRECTION,
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    ATTR_SPEED,
    ATTR_SPEED_LIST,
    ATTR_DIRECTION,
    DOMAIN,
    ENTITY_ID_FORMAT
)

try:
    from homeassistant.components.fan import (
        FanEntity,
        PLATFORM_SCHEMA,
    )
except ImportError:
    from homeassistant.components.fan import (
        FanDevice as FanEntity,
        PLATFORM_SCHEMA,
    )
    
from homeassistant.const import (CONF_MAC)

__version__ = "0.0.1"

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 30
SCAN_INTERVAL = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAC, default=''): cv.string,
})

SUPPORT_FEATURES = SUPPORT_SET_SPEED | SUPPORT_DIRECTION 

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lasko-BT-Fan platform."""
    mac = config.get(CONF_MAC)

    device = LaskoFanDevice(mac)

    add_entities([LaskoBTFanEntity(mac, 'LaskoBTFan', device)], True)

class LaskoBTFanEntity(FanEntity):

    def __init__(self, mac, name, device):
        self._mac = mac
        self._name = '{}-{}'.format(name, mac)
        self.device = device
        self.device.connect()
        self.__refresh_status()

    async def async_added_to_hass(self):
        self.device.set_notify(self.__notify_callback)

    def __notify_callback(self):
        self.__refresh_status
        self.async_schedule_update_ha_state()

    def __refresh_status(self):
        self._state = self.device.power_on

    def set_speed(self, speed: str) -> None:
        if speed == SPEED_OFF:
            self.turn_off()
        else:
            self.device.set_speed(speed)

    def set_direction(self, direction: str) -> None:
        self.device.set_direction(direction)
        
    def turn_off(self, **kwargs) -> None:
        self.device.off()

    def turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        if speed == None:
            self.device.on()
        else: 
            if self.device.power_on == False:
                self.device.on()
            self.device.set_speed(speed)

    @property
    def current_direction(self) -> Optional[str]:
        return self.device.direction

    @property
    def speed_list(self) -> list:
         return [SPEED_OFF,SPEED_LOW,SPEED_MEDIUM,SPEED_HIGH]
    
    @property
    def unique_id(self):
        """Return the ID of this WeMo humidifier."""
        return self._mac

    @property
    def name(self):
        """Return the name of the humidifier if any."""
        return self._name
    
    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_FEATURES
    
    @property
    def speed(self) -> Optional[str]:
        if self.device.power_on == False:
            return SPEED_OFF
        else :
            return self.device.speed

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self.device.power_on
    
    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {}
        
    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self._name,
            "identifiers": {('fan', self._mac)},
            "model": 'W9560',
            "manufacturer": "Lasko",
        }