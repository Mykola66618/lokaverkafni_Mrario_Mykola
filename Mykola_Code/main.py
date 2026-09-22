from machine import Pin, I2C, PWM
import ssd1306
import neopixel
import time


# ==========================================
# HC-SR04
# ==========================================

TRIG_PIN = 5
ECHO_PIN = 4

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)


# ==========================================
# BUTTON
# ==========================================

BUTTON_PIN = 14

button = Pin(
    BUTTON_PIN,
    Pin.IN,
    Pin.PULL_UP
)


# ==========================================
# OLED 128x64
# ==========================================

SCL_PIN = 12
SDA_PIN = 13

i2c = I2C(
    0,
    scl=Pin(SCL_PIN),
    sda=Pin(SDA_PIN)
)

oled = ssd1306.SSD1306_I2C(
    128,
    64,
    i2c
)


# ==========================================
# LED STRIPS
# ==========================================

LED_LEFT_PIN = 42
LED_RIGHT_PIN = 41

LED_COUNT = 10

leds_left = neopixel.NeoPixel(
    Pin(LED_LEFT_PIN),
    LED_COUNT
)

leds_right = neopixel.NeoPixel(
    Pin(LED_RIGHT_PIN),
    LED_COUNT
)


# ==========================================
# SERVO
# ==========================================

SERVO_PIN = 15

servo = PWM(
    Pin(SERVO_PIN),
    freq=50
)


# ==========================================
# SERVO ANGLE
# ==========================================

def servo_angle(angle):

    min_duty = 1638
    max_duty = 8192

    duty = int(
        min_duty
        + (angle / 180)
        * (max_duty - min_duty)
    )

    servo.duty_u16(duty)


# ==========================================
# DISTANCE
# ==========================================

def get_distance():

    # Start ultrasonic pulse
    trig.value(0)
    time.sleep_us(2)

    trig.value(1)
    time.sleep_us(10)

    trig.value(0)

    # Wait for echo
    while echo.value() == 0:
        pass

    start = time.ticks_us()

    while echo.value() == 1:
        pass

    end = time.ticks_us()

    # Calculate pulse duration
    duration = time.ticks_diff(
        end,
        start
    )

    # Convert to centimeters
    distance = duration / 58

    return distance


# ==========================================
# SHOT EFFECT
# ==========================================

def shot_effect():

    # Move servo backwards
    servo_angle(80)

    # Turn LEDs off before animation
    leds_left.fill((0, 0, 0))
    leds_right.fill((0, 0, 0))

    leds_left.write()
    leds_right.write()

    # LED animation
    for i in range(LED_COUNT):

        # LEFT
        leds_left[i] = (
            100,
            0,
            0
        )

        # RIGHT
        leds_right[i] = (
            100,
            0,
            0
        )

        leds_left.write()
        leds_right.write()

        time.sleep_ms(20)

    # Return servo
    servo_angle(30)

    # Keep LEDs on a little
    time.sleep_ms(80)

    # Turn LEDs off
    leds_left.fill((0, 0, 0))
    leds_right.fill((0, 0, 0))

    leds_left.write()
    leds_right.write()


# ==========================================
# START
# ==========================================

# Servo start position
servo_angle(30)


# LEDs OFF
leds_left.fill((0, 0, 0))
leds_right.fill((0, 0, 0))

leds_left.write()
leds_right.write()


# OLED start screen
oled.fill(0)

oled.text(
    "DISTANCE GAME",
    10,
    15
)

oled.text(
    "READY",
    45,
    35
)

oled.show()


print("System ready")


# ==========================================
# MAIN LOOP
# ==========================================

while True:

    # Button pressed
    if button.value() == 0:

        print("SHOT!")

        # ----------------------------------
        # 1. Measure immediately
        # ----------------------------------

        distance = get_distance()


        # ----------------------------------
        # 2. OLED shows SHOT
        # ----------------------------------

        oled.fill(0)

        oled.text(
            "SHOT!",
            45,
            25
        )

        oled.show()


        # ----------------------------------
        # 3. Servo + LED effect
        # ----------------------------------

        shot_effect()


        # ----------------------------------
        # 4. Show result AFTER animation
        # ----------------------------------

        oled.fill(0)

        oled.text(
            "RESULT",
            40,
            8
        )

        oled.text(
            "Distance:",
            25,
            28
        )

        oled.text(
            str(round(distance, 1)) + " cm",
            35,
            45
        )

        oled.show()


        # Serial result
        print(
            "Distance:",
            round(distance, 1),
            "cm"
        )


        # ----------------------------------
        # 5. Protection from holding button
        # ----------------------------------

        while button.value() == 0:

            time.sleep_ms(10)


        # Button debounce
        time.sleep_ms(100)


    time.sleep_ms(10)