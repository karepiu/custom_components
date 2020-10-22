import struct
import time
from collections import namedtuple

import binascii

import logging
from datetime import datetime

import pygatt
from pygatt.exceptions import (
    BLEError, NotConnectedError, NotificationTimeout)

from uuid import UUID

_LOGGER = logging.getLogger(__name__)

# Use full UUID since we do not use UUID from bluepy.btle
CHAR_UUID_MANUFACTURER_NAME = UUID('00002a29-0000-1000-8000-00805f9b34fb')
CHAR_UUID_SERIAL_NUMBER_STRING = UUID('00002a25-0000-1000-8000-00805f9b34fb')
CHAR_UUID_MODEL_NUMBER_STRING = UUID('00002a24-0000-1000-8000-00805f9b34fb')
CHAR_UUID_DEVICE_NAME = UUID('00002a00-0000-1000-8000-00805f9b34fb')

Characteristic = namedtuple('Characteristic', ['uuid', 'name', 'format'])

manufacturer_characteristics = Characteristic(CHAR_UUID_MANUFACTURER_NAME, 'manufacturer', "utf-8")
device_info_characteristics = [manufacturer_characteristics,
                               Characteristic(CHAR_UUID_SERIAL_NUMBER_STRING, 'serial_nr', "utf-8"),
                               Characteristic(CHAR_UUID_MODEL_NUMBER_STRING, 'model_nr', "utf-8"),
                               Characteristic(CHAR_UUID_DEVICE_NAME, 'device_name', "utf-8")]

LASKO_FAN_ON = '0403040108'
LASKO_FAN_OFF = '0403040007'
LASKO_FAN_SPEED_1 = '040307010B'
LASKO_FAN_SPEED_2 = '040307020C'
LASKO_FAN_SPEED_3 = '040307030D'
LASKO_FAN_DIRECTION_FORWARD = '040308010C'
LASKO_FAN_DIRECTION_REVERSE = '040308000B'
LASKO_FAN_DIRECTION_MIXED = '040308020D'
LASKO_FAN_STATE = '03030306'

class LaskoFanDevice:
    def __init__(self, mac='', manufacturer='Chipsea', serial_nr='com3', model_nr='CSM92P10', device_name='Chipsea9210         '):
        self.manufacturer = manufacturer
        self.serial_nr = serial_nr
        self.model_nr = model_nr
        self.device_name = device_name
        self.mac = mac
        self.adapter = pygatt.backends.GATTToolBackend()
        self.connected = False
        self.speed = 'low'
        self.direction = 'reverse'
        self.temp = 0
        self.power_on = False;\
        self.notify = None

    def set_notify(self,func):
        self.notify = func

    def _parse_speed(self,speed):
        if speed == 1:
            self.speed = 'low'
        elif speed == 2:
            self.speed = 'medium'
        else:
            self.speed = 'high'
            
    def _parse_direction(self,direction):
        if direction == 0:
            self.direction = 'reverse'
        elif direction == 1:
            self.direction = 'forward'
        else:
            self.direction = 'mixed'
            
    def _parse_power_on(self,power_on):
        if power_on == 0:
            self.power_on = False
        else :
            self.power_on = True
    
    def _state_parse_sensor(self,value):
        temp = value[4]
        self.temp = temp
        
    def _state_parse_action(self,value):
        action = value[2]
        action_value = value[3]
        if action == 4:
            self._parse_power_on(action_value)
        elif action == 7:
            self._parse_speed(action_value)
        elif action == 8:
            self._parse_direction(action_value)
        else :
            _LOGGER.info("{}: Timer or thermostat button pressed. Alternate control selected.".format(self.mac))
            _LOGGER.info("{}: Please power cycle device to get app control back.".format(self.mac))
   
    def _state_parse_state(self,value):
        power_on = value[3]
        speed = value[5]
        direction = value[7]
        self.temp = value[9]
        self._parse_power_on(power_on)
        self._parse_speed(speed)
        self._parse_direction(direction)

    def notification_handle(self,handle, value):
        #_LOGGER.debug("{}: received data {}".format(self.mac, value))
        _LOGGER.info("{}: before power_on {} speed {} direction {} temp {}".format(self.mac, self.power_on, self.speed, self.direction, self.temp))
        first_byte = value[0]
        if first_byte == 11:
            self._state_parse_state(value)
        elif first_byte == 6:
            self._state_parse_sensor(value)
        elif first_byte == 4:
            self._state_parse_action(value)
        else :
            _LOGGER.info("{}: unknow value".format(self.mac))
        if self.notify != None:
            self.notify()
        _LOGGER.info("{}: after power_on {} speed {} direction {} temp {}".format(self.mac, self.power_on, self.speed, self.direction, self.temp))

    def connect(self):
        try:
            self.adapter.start(reset_on_start=False)
            self.device = self.adapter.connect(self.mac)
            self.connected = True
            _LOGGER.info("{}: connected".format(self.mac))
            self.device.subscribe('0000fff1-0000-1000-8000-00805f9b34fb',callback=self.notification_handle)
            _LOGGER.info("{}: subscribed to notification service".format(self.mac))
            self.state_refresh()
        except (BLEError, NotConnectedError, NotificationTimeout):
            _LOGGER.debug("Failed to connect")
            _LOGGER.info("Failed to connect")
            
    def disconnect(self):
        if self.connected == True:
            try:
                self.device.disconnect()
                self.connected = False
                _LOGGER.info("{}: disconnected".format(self.mac))
            except (BLEError, NotConnectedError, NotificationTimeout):
                _LOGGER.debug("Failed to disconnect")
                _LOGGER.info("Failed to disconnect")
            finally:
                self.adapter.stop()
                
    def state_refresh(self):
        self.device.char_write('0000fff2-0000-1000-8000-00805f9b34fb',bytearray.fromhex(LASKO_FAN_STATE))
    
    def read_characteristics(self):
        for uuid in self.device.discover_characteristics().keys():
            _LOGGER.info("Read UUID {}: {}".format(uuid, binascii.hexlify(self.device.char_read(uuid))))

    def send_command(self,command):
        if self.connected == False:
            self.connect()
        try:
            self.device.char_write('0000fff2-0000-1000-8000-00805f9b34fb',bytearray.fromhex(command))
            self.state_refresh()
        except (BLEError, NotConnectedError, NotificationTimeout):
            self.connect()
            self.state_refresh()
            

    def set_speed(self, speed):
        if speed == 'low':
            self.send_command(LASKO_FAN_SPEED_1)
            self.speed = 'low'
        elif speed == 'medium':      
            self.send_command(LASKO_FAN_SPEED_2)
            self.speed = 'medium'
        elif speed == 'high':         
            self.send_command(LASKO_FAN_SPEED_3)
            self.speed = 'high'
        elif speed == 'off':
            self.send_command(LASKO_FAN_OFF)
            self.power_on = False
            self.speed = 'low'
            self.direction = 'reverse'
        else :
            _LOGGER.info("No such speed")
    
    def set_direction(self, direction):
        if direction == 'forward':
            self.send_command(LASKO_FAN_DIRECTION_FORWARD)
            self.direction = 'forward'
        elif direction == 'reverse':
            self.send_command(LASKO_FAN_DIRECTION_REVERSE)
            self.direction = 'reverse'
        elif direction == 'mixed':
            self.send_command(LASKO_FAN_DIRECTION_MIXED)
            self.direction = 'mixed'
        else :
            _LOGGER.info("No such direction")

    def on(self):
        if self.connected == True:
            self.send_command(LASKO_FAN_ON)
            self.power_on = True
            self.speed = 'low'
            self.direction = 'reverse'
            _LOGGER.info("{}: on".format(self.mac))
        
    def off(self):
        if self.connected == True:
            self.send_command(LASKO_FAN_OFF)
            self.power_on = False
            self.speed = 'low'
            self.direction = 'reverse'
            _LOGGER.info("{}: off".format(self.mac))

    def __del__(self):
        try:
            self.device.disconnect()
        finally:
            self.adapter.stop()

    def __str__(self):
        return "Manufacturer: {} Model: {} Serial: {} Device:{} Mac:{}".format(
            self.manufacturer, self.model_nr, self.serial_nr, self.device_name, self.mac)

class LaskoFanDetect:
    def __init__(self, scan_interval, mac=None):
        self.adapter = pygatt.backends.GATTToolBackend()
        self.fan_devices = [] if mac is None else [mac]
        self.scan_interval = scan_interval
        self.last_scan = -1


    def find_devices_macs(self):
        # Scan for devices and try to figure out if it is an airthings device.
        self.adapter.start(reset_on_start=False)
        devices = self.adapter.scan(timeout=3)
        self.adapter.stop()

        for device in devices:
            mac = device['address']
            _LOGGER.debug("connecting to {}".format(mac))
            try:
                self.adapter.start(reset_on_start=False)
                dev = self.adapter.connect(mac, 3)
                _LOGGER.debug("Connected")
                try:
                    data = dev.char_read(manufacturer_characteristics.uuid)
                    manufacturer_name = data.decode(manufacturer_characteristics.format)
                    if "chipsea" in manufacturer_name.lower():
                        self.fan_devices.append(mac)
                except (BLEError, NotConnectedError, NotificationTimeout):
                    _LOGGER.debug("connection to {} failed".format(mac))
                finally:
                    dev.disconnect()
            except (BLEError, NotConnectedError, NotificationTimeout):
                _LOGGER.debug("Failed to connect")
            finally:
                self.adapter.stop()

        _LOGGER.debug("Found {} Lasko BT Fans devices".format(len(self.fan_devices)))
        return self.fan_devices

    def find_devices(self):
        # Try to get some info from the discovered airthings devices
        self.devices = {}

        if len(self.fan_devices) == 0: self.find_devices_macs()

        for device_mac in self.fan_devices:
            device = LaskoFanDevice(mac=device_mac,serial_nr=device_mac)
            try:
                self.adapter.start(reset_on_start=False)
                dev = self.adapter.connect(device_mac, 3)
                for characteristic in device_info_characteristics:
                    try:
                        data = dev.char_read(characteristic.uuid)
                        setattr(device, characteristic.name, data.decode(characteristic.format))
                    except (BLEError, NotConnectedError, NotificationTimeout):
                        _LOGGER.exception("")
                dev.disconnect()
            except (BLEError, NotConnectedError, NotificationTimeout):
                _LOGGER.exception("")
            self.adapter.stop()
            self.devices[device_mac] = device

        return self.devices

if __name__ == "__main__":
    logging.basicConfig()
    _LOGGER.setLevel(logging.INFO)
    lfd = LaskoFanDetect(180)
#    devs_found = lfd.find_devices_macs()
#    if len(devs_found) > 0:
#        devices = lfd.find_devices()
#        for mac, dev in devices.items():
#            _LOGGER.info("{}: {}".format(mac, dev))



