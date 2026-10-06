from machine import Pin, I2C
import ssd1306
import neopixel
import network
import time
from umqtt.simple import MQTTClient


# ==========================================
# PLAYER 2
# ==========================================

MY_PLAYER = 2


# ==========================================
# WIFI + MQTT
# ==========================================

WIFI_NAME = "TskoliVESM"
WIFI_PASSWORD = "Fallegurhestur"

MQTT_SERVER = "10.201.48.133"

MY_SHOT_TOPIC = b"game/player2/shot"

TARGET_TOPIC = b"game/target"
PLAYER_TOPIC = b"game/player"
RESULT_TOPIC = b"game/result"
NEW_ROUND_TOPIC = b"game/new_round"


# ==========================================
# PINS
# ==========================================

TRIG_PIN = 5
ECHO_PIN = 4
BUTTON_PIN = 14

OLED_SCL = 12
OLED_SDA = 13

LED_LEFT_PIN = 42
LED_RIGHT_PIN = 41

LED_COUNT = 8


# ==========================================
# HARDWARE
# ==========================================

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

button = Pin(
    BUTTON_PIN,
    Pin.IN,
    Pin.PULL_UP
)

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


# ==========================================
# GAME VARIABLES
# ==========================================

target = 0
current_player = 1
game_finished = False


# ==========================================
# LED
# ==========================================

def clear_leds():

    for i in range(LED_COUNT):

        led_left[i] = (0, 0, 0)
        led_right[i] = (0, 0, 0)

    led_left.write()
    led_right.write()


def shot_effect():

    clear_leds()

    for i in range(LED_COUNT):

        led_left[i] = (0, 0, 100)
        led_right[i] = (0, 0, 100)

        led_left.write()
        led_right.write()

        time.sleep_ms(30)

    time.sleep_ms(150)

    clear_leds()


clear_leds()


# ==========================================
# DISTANCE SENSOR
# ==========================================

def get_distance():

    trig.value(0)
    time.sleep_us(2)

    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

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

    return duration / 58


# ==========================================
# OLED
# ==========================================

def show_waiting():

    oled.fill(0)

    oled.text(
        "DISTANCE DUEL",
        10,
        5
    )

    oled.text(
        "PLAYER 2",
        30,
        25
    )

    oled.text(
        "WAIT...",
        40,
        45
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
        "PLAYER 2",
        30,
        25
    )

    oled.text(
        "YOUR TURN!",
        25,
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


# ==========================================
# WIFI
# ==========================================

def connect_wifi():

    wifi = network.WLAN(
        network.STA_IF
    )

    wifi.active(True)

    if wifi.isconnected():

        print("WiFi connected")

        return wifi

    print("Connecting WiFi...")

    wifi.connect(
        WIFI_NAME,
        WIFI_PASSWORD
    )

    while not wifi.isconnected():

        print(".")
        time.sleep(1)

    print("WiFi connected!")

    print(
        "IP:",
        wifi.ifconfig()[0]
    )

    return wifi


# ==========================================
# MQTT CALLBACK
# ==========================================

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

        if current_player == MY_PLAYER:
            show_game()
        else:
            show_waiting()

    # CURRENT PLAYER
    elif topic == PLAYER_TOPIC:

        try:
            current_player = int(message)
        except:
            return

        game_finished = False

        if current_player == MY_PLAYER:

            print("PLAYER 2 TURN")
            show_game()

        else:

            print("Waiting for Player 1")
            show_waiting()

    # RESULT
    elif topic == RESULT_TOPIC:

        game_finished = True

        oled.fill(0)

        oled.text(
            "ROUND FINISHED",
            5,
            5
        )

        if "PLAYER 2" in message:

            oled.text(
                "YOU WIN!",
                30,
                30
            )

        elif "PLAYER 1" in message:

            oled.text(
                "PLAYER 1",
                30,
                22
            )

            oled.text(
                "WINS",
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


# ==========================================
# CONNECT WIFI + MQTT
# ==========================================

wifi = connect_wifi()

show_waiting()

print("Connecting MQTT...")

# IMPORTANT:
# different MQTT client ID
client = MQTTClient(
    "distance_blaster_2",
    MQTT_SERVER
)

client.set_callback(
    mqtt_message
)

client.connect()

client.subscribe(TARGET_TOPIC)
client.subscribe(PLAYER_TOPIC)
client.subscribe(RESULT_TOPIC)

print("PLAYER 2 READY!")


# ==========================================
# BUTTON
# ==========================================

def button_action():

    global game_finished

    press_start = time.ticks_ms()


    # ======================================
    # CHECK LONG PRESS
    # ======================================

    while button.value() == 0:

        client.check_msg()

        press_time = time.ticks_diff(
            time.ticks_ms(),
            press_start
        )

        # Player 2 can also request
        # a new round after 2 seconds
        if press_time >= 2000:

            show_new_round()

            print("NEW ROUND requested")

            client.publish(
                NEW_ROUND_TOPIC,
                b"1"
            )

            while button.value() == 0:

                client.check_msg()
                time.sleep_ms(20)

            time.sleep_ms(300)

            return

        time.sleep_ms(10)


    # ======================================
    # SHORT PRESS
    # ======================================

    if game_finished:

        print(
            "Round finished. Hold button for new round."
        )

        return


    if current_player != MY_PLAYER:

        print(
            "NOT PLAYER 2 TURN"
        )

        show_waiting()

        return


    # ======================================
    # PLAYER 2 SHOT
    # ======================================

    print("PLAYER 2 SHOT")

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


    # SHOT SCREEN

    oled.fill(0)

    oled.text(
        "PLAYER 2",
        30,
        15
    )

    oled.text(
        "SHOT!",
        45,
        35
    )

    oled.show()


    # LED EFFECT

    shot_effect()


    # DISTANCE

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
        "PLAYER 2 DISTANCE:",
        distance
    )


    # SEND TO RASPBERRY

    client.publish(
        MY_SHOT_TOPIC,
        str(distance)
    )

    time.sleep_ms(300)


# ==========================================
# MAIN LOOP
# ==========================================

while True:

    try:

        client.check_msg()

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

            client.subscribe(TARGET_TOPIC)
            client.subscribe(PLAYER_TOPIC)
            client.subscribe(RESULT_TOPIC)

            print("MQTT reconnected")

        except Exception as error:

            print(
                "Reconnect failed:",
                error
            )
