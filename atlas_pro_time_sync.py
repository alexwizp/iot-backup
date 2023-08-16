import time
import datetime
import ujson
import urequests as requests
import network
from machine import Pin, SoftI2C, RTC, UART
from ds3231 import DS3231
import datetime
import webrepl

# Configuration
ap_ssid = "{ap_ssid}"
ap_password = "{ap_password}"
webrtl_password = "{webrtl_password}"
ipgeolocaiton_api_key = "{ipgeolocaiton_api_key}"
sync_time_interval_ms = 3600000 * 2  # 2 hours
head_unit_timezone_offset = 3 #in hours

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

def log(*log_args):
    print(log_args)


def init_i2c():
    i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
    devices = i2c.scan()

    if len(devices) == 0:
        log("[I2C] No connected devices!")
    else:
        log("[I2C] Devices found:", len(devices))

    for device in devices:
        log("[I2C] At address: ", hex(device))

    return i2c


def init_uart():
    uart = UART(2, 921600)
    uart.init(921600, bits=8, parity=None, stop=1)

    return uart


def do_wifi_connect(ssid, password):
    wlan_sta.active(True)
    
    connected = wlan_sta.isconnected()
        
    if connected:
        webrepl.start(password=webrtl_password)
        log("[WiFi] Connected. Network config: ", wlan_sta.ifconfig())
    else:
        log("[WiFi] Trying to connect to %s..." % ssid)
        wlan_sta.connect(ssid, password)
        for retry in range(200):
          connected = wlan_sta.isconnected()
          if connected:
            log("[WiFi] Connected.")
            return True
          time.sleep(0.1)
          log(".", end="")
        log("[WiFi] Failed. Not Connected to: " + ssid)

    return connected

def get_ipgeolocaiton_timestamp():
    raw_response = requests.get(
        url="https://api.ipgeolocation.io/ipgeo?apiKey=" + ipgeolocaiton_api_key
    ).text
    data = ujson.loads(raw_response)
    local_offset = int(data["time_zone"]["offset_with_dst"])
   
    with_heatunit_offset = local_offset + (local_offset - head_unit_timezone_offset)
    geo_time = datetime.datetime.fromisoformat((data["time_zone"]["current_time"])[0:19])
    
    return geo_time - datetime.timedelta(seconds = with_heatunit_offset * 60 * 60)

def update_head_unit_time():
    # In ESP32 epoch time is started from 01/01/2020. In unix this value is equal to January 1, 1970.
    epoch_time_offset = 946684800;
    command = "date " + str(time.time() + epoch_time_offset) + " \r"
    log("[UART] Write command:", command)
    uart.write(command)
    log("[UART] Executed with result:", uart.readline())
    

def main_loop():
    last_time_synchronized = -1 * sync_time_interval_ms
    cycle = 1

    while cycle:
        wlan_connected = wlan_sta.isconnected()
        wlan_just_connected = False
        ticks_ms = time.ticks_ms()

        if wlan_connected == False:
            try:
                wlan_connected = do_wifi_connect(ap_ssid, ap_password)
                wlan_connected_changed = True
            except:
                log("[WiFi] Failed")
                      

        if (
            wlan_connected == True
            and (last_time_synchronized + sync_time_interval_ms < ticks_ms or wlan_just_connected)
        ):
            try:
                geo_time = get_ipgeolocaiton_timestamp()
                  
                rtc_external.datetime(
                    (
                        geo_time.year,
                        geo_time.month,
                        geo_time.day,
                        geo_time.hour,
                        geo_time.minute,
                        geo_time.second,
                    )
                )
                last_time_synchronized = ticks_ms
                log("[Time Synchronization] Executed", rtc_external.datetime())
                
                if cycle > 4:
                    update_head_unit_time()
            
            except:
                log("[Time Synchronization] Failed")
                

        if cycle > 1 and cycle < 4:
            try:
                update_head_unit_time()
            except:
                log("[UART] Failed")

        cycle += 1
        
        time.sleep(15)


if __name__ == "__main__":
    i2c = init_i2c()
    uart = init_uart()
    rtc_external = DS3231(i2c)
    rtc = RTC()
    rtc.init(rtc_external.datetime())
    
    log("[RTC] Initial time: ", rtc.datetime())

    main_loop()
