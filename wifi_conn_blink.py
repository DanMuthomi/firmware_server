import network
import secrets
import time
import blink
import machine

led = machine.Pin('LED', machine.Pin.OUT) #configure LED Pin as an output pin and create and led object for Pin class

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

while not wlan.isconnected():
    print("Connecting to Wi-Fi...")
    wlan.connect(secrets.SSID, secrets.PASSWORD)
    time.sleep(10)  # Wait for 10 seconds before trying again

print("Connect successful")
blink.blinking()