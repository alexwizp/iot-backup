import time
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
sync_time_interval_ms = 3600000 * 2  # 2h
push_time_interval_ms = 60000


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


def format_date(year, month, day, hours, minutes, seconds):
    formatter_year = f"{year:0>{4}}"
    formatted_month = f"{month:0>{2}}"
    formatted_day = f"{day:0>{2}}"
    formatted_hours = f"{hours:0>{2}}"
    formatted_minutes = f"{minutes:0>{2}}"
    formatted_seconds = f"{seconds:0>{2}}"

    return (
        formatted_month
        + formatted_day
        + formatted_hours
        + formatted_minutes
        + formatter_year
        + "."
        + formatted_seconds
    )


def get_ipgeolocaiton_time():
    raw_response = requests.get(
        url="https://api.ipgeolocation.io/ipgeo?apiKey=" + ipgeolocaiton_api_key
    ).text
    data = ujson.loads(raw_response)

    return datetime.datetime.fromisoformat((data["time_zone"]["current_time"])[0:19])


def main_loop():
    last_time_synchronized = -1 * sync_time_interval_ms
    last_push_time = -1 * push_time_interval_ms

    while True:
        wlan_connected = wlan_sta.isconnected()
        ticks_ms = time.ticks_ms()

        if wlan_connected == False:
            try:
                wlan_connected = do_wifi_connect(ap_ssid, ap_password)
            except:
                log("[WiFi] Failed")

        if (
            wlan_connected == True
            and last_time_synchronized + sync_time_interval_ms < ticks_ms
        ):
            try:
                geo_time = get_ipgeolocaiton_time()
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
            except:
                log("[Time Synchronization] Failed")

        if last_push_time + push_time_interval_ms < ticks_ms:
            try:
                (
                    year,
                    month,
                    day,
                    weekday,
                    hours,
                    minutes,
                    seconds,
                    subseconds,
                ) = rtc.datetime()
                command = "date " + format_date(
                    year, month, day, hours, minutes, seconds
                )
                log("[UART] Write command:", command)
                uart.write(command)
                last_push_time = ticks_ms
                log("[UART] Executed with result:", uart.readline())
            except:
                log("[UART] Failed")

        time.sleep(10)


if __name__ == "__main__":
    i2c = init_i2c()
    uart = init_uart()
    rtc_external = DS3231(i2c)
    rtc = RTC()
    rtc.init(rtc_external.datetime())

    (year, month, day, weekday, hours, minutes, seconds, subseconds) = rtc.datetime()
    log(
        "[RTC] Initial time: ", format_date(year, month, day, hours, minutes, seconds)
    )

    main_loop()

