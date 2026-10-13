
from machine import Pin, I2C
import ssd1306
import neopixel
import network
import time
from umqtt.simple import MQTTClient

# =====================================
# PLAYER 2 - BLUE
# =====================================

MY_PLAYER = 2
MQTT_CLIENT_ID = b"distance_blaster_2"

WIFI_NAME = "TskoliVESM"
WIFI_PASSWORD = "Fallegurhestur"
MQTT_SERVER = "10.201.48.133"

MY_SHOT_TOPIC = b"game/player2/shot"
TARGET_TOPIC = b"game/target"
PLAYER_TOPIC = b"game/player"
RESULT_TOPIC = b"game/result"
NEW_ROUND_TOPIC = b"game/new_round"

# =====================================
# PINS
# =====================================

TRIG_PIN = 5
ECHO_PIN = 4
BUTTON_PIN = 14

OLED_SCL = 17
OLED_SDA = 16

LED_LEFT_PIN = 42
LED_RIGHT_PIN = 36
LED_COUNT = 8

SHOT_COLOR = (0, 0, 100)

# =====================================
# HARDWARE
# =====================================

trig = Pin(TRIG_PIN, Pin.OUT)
trig.value(0)

echo = Pin(ECHO_PIN, Pin.IN)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

i2c = I2C(
    0,
    scl=Pin(OLED_SCL),
    sda=Pin(OLED_SDA),
    freq=100000
)

devices = i2c.scan()
print("OLED devices:", devices)

oled = None

if 0x3C in devices:
    oled = ssd1306.SSD1306_I2C(
        128, 64, i2c, addr=0x3C
    )
elif 0x3D in devices:
    oled = ssd1306.SSD1306_I2C(
        128, 64, i2c, addr=0x3D
    )
else:
    print("WARNING: OLED NOT FOUND!")

led_left = neopixel.NeoPixel(
    Pin(LED_LEFT_PIN, Pin.OUT),
    LED_COUNT
)

led_right = neopixel.NeoPixel(
    Pin(LED_RIGHT_PIN, Pin.OUT),
    LED_COUNT
)

# =====================================
# GAME STATE
# =====================================

target = 0
round_ready = False
has_shot = False
game_finished = False

wifi = network.WLAN(network.STA_IF)
client = None

# =====================================
# OLED
# =====================================

def show_screen(a="", b="", c=""):
    print("SCREEN:", a, "|", b, "|", c)

    if oled is None:
        return

    oled.fill(0)
    oled.text(str(a)[:16], 0, 5)
    oled.text(str(b)[:16], 0, 25)
    oled.text(str(c)[:16], 0, 45)
    oled.show()


def show_game():
    if game_finished:
        return

    if not round_ready:
        show_screen(
            "PLAYER 2",
            "WAITING...",
            "FOR TARGET"
        )

    elif has_shot:
        show_screen(
            "TARGET: " + str(target),
            "SHOT SENT!",
            "WAIT PLAYER 1"
        )

    else:
        show_screen(
            "TARGET: " + str(target),
            "PLAYER 2 READY",
            "PRESS TO SHOOT"
        )


def show_result(result):
    if result == "DRAW":
        show_screen(
            "ROUND FINISHED",
            "DRAW!",
            "HOLD = NEW"
        )

    elif result == "PLAYER 2":
        show_screen(
            "ROUND FINISHED",
            "YOU WIN!",
            "HOLD = NEW"
        )

    elif result == "PLAYER 1":
        show_screen(
            "ROUND FINISHED",
            "YOU LOSE!",
            "HOLD = NEW"
        )

# =====================================
# LED
# =====================================

def set_leds(color):
    for i in range(LED_COUNT):
        led_left[i] = color
        led_right[i] = color

    led_left.write()
    led_right.write()


def clear_leds():
    set_leds((0, 0, 0))


def shot_effect():
    clear_leds()

    for i in range(LED_COUNT):
        led_left[i] = SHOT_COLOR
        led_right[i] = SHOT_COLOR

        led_left.write()
        led_right.write()

        time.sleep_ms(35)

    time.sleep_ms(120)
    clear_leds()


clear_leds()

# =====================================
# ULTRASONIC SENSOR
# =====================================

def get_distance():
    trig.value(0)
    time.sleep_us(2)

    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    start_wait = time.ticks_us()

    while echo.value() == 0:
        if time.ticks_diff(
            time.ticks_us(), start_wait
        ) > 30000:
            return None

    start = time.ticks_us()

    while echo.value() == 1:
        if time.ticks_diff(
            time.ticks_us(), start
        ) > 30000:
            return None

    duration = time.ticks_diff(
        time.ticks_us(), start
    )

    distance = round(duration / 58.0, 1)

    if distance < 2 or distance > 400:
        return None

    return distance

# =====================================
# WIFI
# =====================================

def connect_wifi():
    wifi.active(True)

    if wifi.isconnected():
        return

    print("Connecting WiFi...")
    show_screen(
        "PLAYER 2",
        "CONNECTING",
        "WIFI..."
    )

    wifi.connect(
        WIFI_NAME,
        WIFI_PASSWORD
    )

    start = time.ticks_ms()

    while not wifi.isconnected():
        if time.ticks_diff(
            time.ticks_ms(), start
        ) > 15000:
            raise OSError("WiFi timeout")

        time.sleep_ms(300)

    print("WIFI CONNECTED:", wifi.ifconfig()[0])

# =====================================
# MQTT MESSAGE
# =====================================

def mqtt_message(topic, payload):
    global target
    global round_ready
    global has_shot
    global game_finished

    message = payload.decode().strip()

    print("MQTT:", topic, message)

    if topic == TARGET_TOPIC:
        try:
            new_target = int(message)
        except ValueError:
            return

        if new_target < 20 or new_target > 100:
            return

        target = new_target
        round_ready = True
        has_shot = False
        game_finished = False

        clear_leds()
        show_game()

    elif topic == PLAYER_TOPIC:
        if message == "0":
            show_game()

    elif topic == RESULT_TOPIC:

        # Ignore empty/invalid result messages.
        if message not in (
            "PLAYER 1",
            "PLAYER 2",
            "DRAW"
        ):
            return

        if not round_ready:
            return

        game_finished = True

        show_result(message)

        if message == "PLAYER 2":
            set_leds((0, 100, 0))

        elif message == "DRAW":
            set_leds((100, 100, 0))

        else:
            set_leds((100, 0, 0))

# =====================================
# MQTT CONNECTION
# =====================================

def connect_mqtt():
    global client

    if client is not None:
        try:
            client.disconnect()
        except Exception:
            pass

    client = MQTTClient(
        MQTT_CLIENT_ID,
        MQTT_SERVER,
        port=1883,
        keepalive=60
    )

    client.set_callback(mqtt_message)
    client.connect()

    client.subscribe(TARGET_TOPIC)
    client.subscribe(PLAYER_TOPIC)
    client.subscribe(RESULT_TOPIC)

    print("PLAYER 2 MQTT CONNECTED")

# =====================================
# BUTTON
# =====================================

def button_action():
    global has_shot

    press_start = time.ticks_ms()

    # Wait to find out: short or long press.
    while button.value() == 0:
        client.check_msg()

        press_time = time.ticks_diff(
            time.ticks_ms(),
            press_start
        )

        if press_time >= 2000:
            print("REQUEST NEW ROUND")

            show_screen(
                "NEW ROUND",
                "REQUEST SENT",
                "RELEASE BTN"
            )

            client.publish(
                NEW_ROUND_TOPIC,
                b"1"
            )

            # Only one request per long press.
            while button.value() == 0:
                client.check_msg()
                time.sleep_ms(20)

            time.sleep_ms(60)
            show_game()
            return

        time.sleep_ms(15)

    # Debounce after release.
    time.sleep_ms(30)

    # Short press.
    if not round_ready:
        print("NO TARGET YET")
        show_game()
        return

    if game_finished:
        print("ROUND FINISHED")
        return

    if has_shot:
        print("ALREADY SHOT")
        return

    distance = get_distance()

    if distance is None:
        print("SENSOR ERROR")

        show_screen(
            "SENSOR ERROR",
            "CHECK SENSOR",
            "TRY AGAIN"
        )

        time.sleep_ms(700)
        show_game()
        return

    print("PLAYER 2 SHOT:", distance)

    show_screen(
        "PLAYER 2 SHOT",
        str(distance) + " cm",
        "SENDING..."
    )

    # Send BEFORE animation.
    client.publish(
        MY_SHOT_TOPIC,
        str(distance).encode()
    )

    has_shot = True

    print("SHOT SENT!")

    shot_effect()

    # Process result if it arrived during animation.
    client.check_msg()
    show_game()

# =====================================
# MAIN
# =====================================

show_screen(
    "DISTANCE DUEL",
    "PLAYER 2",
    "STARTING..."
)

while True:
    try:
        if not wifi.isconnected():
            connect_wifi()

        if client is None:
            connect_mqtt()
            show_game()

        client.check_msg()

        if button.value() == 0:
            button_action()

        time.sleep_ms(20)

    except OSError as error:
        print("CONNECTION ERROR:", error)

        show_screen(
            "CONNECTION LOST",
            "RECONNECTING",
            "PLEASE WAIT"
        )

        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass

        client = None

        time.sleep(2)

