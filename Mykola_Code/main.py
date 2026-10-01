from machine import Pin, I2C, PWM
import ssd1306
import neopixel
import network
import time
from umqtt.simple import MQTTClient


# =========================
# WIFI + MQTT
# =========================

WIFI_NAME = "TskoliVESM"
WIFI_PASSWORD = "Fallegurhestur"

# Поставь актуальный IP Raspberry Pi
MQTT_SERVER = "10.201.48.133"

SHOT_TOPIC = b"game/shot"
TARGET_TOPIC = b"game/target"
PLAYER_TOPIC = b"game/player"
RESULT_TOPIC = b"game/result"
NEW_ROUND_TOPIC = b"game/new_round"


# =========================
# PINS
# =========================

TRIG_PIN = 5
ECHO_PIN = 4
BUTTON_PIN = 14

OLED_SCL = 12
OLED_SDA = 13

LED_LEFT_PIN = 42
LED_RIGHT_PIN = 41
LED_COUNT = 10

SERVO_PIN = 15


# =========================
# HARDWARE
# =========================

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

i2c = I2C(
    0,
    scl=Pin(OLED_SCL),
    sda=Pin(OLED_SDA)
)

oled = ssd1306.SSD1306_I2C(
    128,
    64,
    i2c
)

led_left = neopixel.NeoPixel(
    Pin(LED_LEFT_PIN),
    LED_COUNT
)

led_right = neopixel.NeoPixel(
    Pin(LED_RIGHT_PIN),
    LED_COUNT
)

servo = PWM(
    Pin(SERVO_PIN),
    freq=50
)


# =========================
# GAME VARIABLES
# =========================

target = 0
current_player = 1
game_finished = False


# =========================
# SERVO
# =========================

def servo_angle(angle):
    min_duty = 1638
    max_duty = 8192

    duty = int(
        min_duty +
        (angle / 180) *
        (max_duty - min_duty)
    )

    servo.duty_u16(duty)


servo_angle(30)


# =========================
# LED
# =========================

def clear_leds():

    for i in range(LED_COUNT):
        led_left[i] = (0, 0, 0)
        led_right[i] = (0, 0, 0)

    led_left.write()
    led_right.write()


clear_leds()


# =========================
# DISTANCE SENSOR
# =========================

def get_distance():

    trig.value(0)
    time.sleep_us(2)

    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    # timeout protection
    start_wait = time.ticks_us()

    while echo.value() == 0:

        if time.ticks_diff(
            time.ticks_us(),
            start_wait
        ) > 30000:

            return None

    start = time.ticks_us()

    while echo.value() == 1:

        if time.ticks_diff(
            time.ticks_us(),
            start
        ) > 30000:

            return None

    end = time.ticks_us()

    duration = time.ticks_diff(
        end,
        start
    )

    distance = duration / 58

    return distance


# =========================
# SHOT EFFECT
# =========================

def shot_effect():

    servo_angle(80)

    clear_leds()

    for i in range(LED_COUNT):

        led_left[i] = (100, 0, 0)
        led_right[i] = (100, 0, 0)

        led_left.write()
        led_right.write()

        time.sleep_ms(20)

    servo_angle(30)

    time.sleep_ms(80)

    clear_leds()


# =========================
# OLED
# =========================

def show_ready():

    oled.fill(0)

    oled.text(
        "DISTANCE DUEL",
        10,
        10
    )

    oled.text(
        "READY TO PLAY",
        10,
        30
    )

    oled.text(
        "Hold = New Round",
        0,
        50
    )

    oled.show()


def show_game():

    oled.fill(0)

    oled.text(
        "TARGET: " + str(target),
        10,
        5
    )

    oled.text(
        "PLAYER " + str(current_player),
        25,
        25
    )

    oled.text(
        "PRESS BUTTON",
        15,
        45
    )

    oled.show()


def show_new_round():

    oled.fill(0)

    oled.text(
        "NEW ROUND",
        25,
        25
    )

    oled.show()


# =========================
# WIFI
# =========================

def connect_wifi():

    wifi = network.WLAN(
        network.STA_IF
    )

    wifi.active(True)

    if wifi.isconnected():
        return wifi

    print("Connecting to WiFi...")

    if WIFI_PASSWORD == "":
        wifi.connect(WIFI_NAME)
    else:
        wifi.connect(
            WIFI_NAME,
            WIFI_PASSWORD
        )

    while not wifi.isconnected():

        print(".")

        time.sleep(1)

    print("WiFi connected!")
    print(
        "ESP32 IP:",
        wifi.ifconfig()[0]
    )

    return wifi


# =========================
# MQTT CALLBACK
# =========================

def mqtt_message(topic, message):

    global target
    global current_player
    global game_finished

    message = message.decode()

    print(
        "MQTT:",
        topic,
        message
    )

    # TARGET
    if topic == TARGET_TOPIC:

        try:
            target = int(message)
        except:
            return

        game_finished = False

        show_game()

    # PLAYER
    elif topic == PLAYER_TOPIC:

        try:
            current_player = int(message)
        except:
            return

        game_finished = False

        show_game()

    # RESULT
    elif topic == RESULT_TOPIC:

        game_finished = True

        oled.fill(0)

        oled.text(
            "ROUND FINISHED",
            5,
            5
        )

        if "PLAYER 1" in message:

            oled.text(
                "PLAYER 1",
                30,
                25
            )

            oled.text(
                "WINS!",
                45,
                42
            )

        elif "PLAYER 2" in message:

            oled.text(
                "PLAYER 2",
                30,
                25
            )

            oled.text(
                "WINS!",
                45,
                42
            )

        else:

            oled.text(
                "DRAW!",
                40,
                30
            )

        oled.show()


# =========================
# CONNECT MQTT
# =========================

wifi = connect_wifi()

show_ready()

print("Connecting MQTT...")

client = MQTTClient(
    "distance_blaster_1",
    MQTT_SERVER
)

client.set_callback(
    mqtt_message
)

client.connect()

client.subscribe(
    TARGET_TOPIC
)

client.subscribe(
    PLAYER_TOPIC
)

client.subscribe(
    RESULT_TOPIC
)

print("MQTT connected!")
print("System ready!")


# =========================
# BUTTON
# =========================

def button_action():

    global game_finished

    press_start = time.ticks_ms()

    long_press = False

    # Button is being held
    while button.value() == 0:

        client.check_msg()

        press_time = time.ticks_diff(
            time.ticks_ms(),
            press_start
        )

        # HOLD FOR 2 SECONDS
        if press_time >= 2000:

            long_press = True

            show_new_round()

            print(
                "NEW ROUND requested"
            )

            client.publish(
                NEW_ROUND_TOPIC,
                b"1"
            )

            # Wait until button released
            while button.value() == 0:

                client.check_msg()

                time.sleep_ms(20)

            time.sleep_ms(300)

            return

        time.sleep_ms(10)

    # =====================
    # SHORT PRESS = SHOT
    # =====================

    if not long_press:

        if game_finished:

            print(
                "Round finished. "
                "Hold button for new round."
            )

            return

        print(
            "PLAYER",
            current_player,
            "SHOT"
        )

        distance = get_distance()

        if distance is None:

            oled.fill(0)

            oled.text(
                "SENSOR ERROR",
                10,
                25
            )

            oled.show()

            time.sleep(1)

            show_game()

            return

        distance = round(
            distance,
            1
        )

        # SHOT screen
        oled.fill(0)

        oled.text(
            "PLAYER " +
            str(current_player),
            25,
            15
        )

        oled.text(
            "SHOT!",
            45,
            35
        )

        oled.show()

        # servo + LEDs
        shot_effect()

        # result
        oled.fill(0)

        oled.text(
            "DISTANCE",
            30,
            10
        )

        oled.text(
            str(distance) + " cm",
            25,
            35
        )

        oled.show()

        print(
            "Distance:",
            distance,
            "cm"
        )

        # Send to Raspberry Pi
        client.publish(
            SHOT_TOPIC,
            str(distance)
        )

        time.sleep_ms(300)


# =========================
# START SCREEN
# =========================

show_ready()


# =========================
# MAIN LOOP
# =========================

while True:

    try:

        # Receive MQTT messages
        client.check_msg()

        # Button pressed
        if button.value() == 0:

            button_action()

        time.sleep_ms(20)

    except OSError as error:

        print(
            "MQTT ERROR:",
            error
        )

        time.sleep(2)

        try:

            client.connect()

            client.subscribe(
                TARGET_TOPIC
            )

            client.subscribe(
                PLAYER_TOPIC
            )

            client.subscribe(
                RESULT_TOPIC
            )

            print(
                "MQTT reconnected"
            )

        except:

            print(
                "Reconnect failed"
            )
