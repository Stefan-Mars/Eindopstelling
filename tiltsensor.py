from machine import Pin, PWM
import time

# Pins
tiltsensor = Pin(15, Pin.IN, Pin.PULL_UP)
red = Pin(38, Pin.OUT)
yellow = Pin(37, Pin.OUT)
green = Pin(36, Pin.OUT)
reset_button = Pin(0, Pin.IN, Pin.PULL_UP)


SAMPLE_INTERVAL = 0.1
WINDOW_SECONDS = 1.0
BUFFER_SIZE = int(WINDOW_SECONDS / SAMPLE_INTERVAL)
if BUFFER_SIZE < 2:
    BUFFER_SIZE = 2

tilt_buffer = [tiltsensor.value()] * BUFFER_SIZE
buffer_index = 0

# Hoeveel vibraties achter elkaar om mee te tellen tot de secondes
VIBRATION_TRANSITIONS_THRESHOLD = 1

# Servo configuration (GPIO18)
SERVO_PIN = 18
SERVO_FREQ = 50
# pulse widths in microseconds for typical servos (adjust if needed)
SERVO_MIN_US = 500
SERVO_MAX_US = 2400
SERVO_REST_US = SERVO_MIN_US
SERVO_ENGAGED_US = SERVO_MAX_US

# Initialize servo PWM
pwm_servo = PWM(Pin(SERVO_PIN), freq=SERVO_FREQ)
def set_servo_pulse(us):
    # 50Hz -> period = 20000us. PWM duty range 0-1023 on many builds.
    duty = int(us * 1023 / 20000)
    pwm_servo.duty(duty)

# start at rest
set_servo_pulse(SERVO_REST_US)

# Track whether servo is currently engaged (turned)
servo_engaged = False

def set_light(active):
    red.off()
    yellow.off()
    green.off()
    active.on()

vibrating = False
vibration_start = None
locked = False
latched_status = 'VEILIG'

while True:
    tiltwaarde = tiltsensor.value()
    tilt_buffer[buffer_index] = tiltwaarde
    buffer_index = (buffer_index + 1) % BUFFER_SIZE

    # Hoeveel trillingen achter elkaar
    transitions = sum(tilt_buffer[i] != tilt_buffer[i-1] for i in range(1, BUFFER_SIZE))

    # De trillingen die achter elkaar staan die worden hier gecheckt
    if transitions > VIBRATION_TRANSITIONS_THRESHOLD:
        if not vibrating:
            vibrating = True
            vibration_start = time.ticks_ms()
    else:
        if vibrating:
            vibrating = False
            vibration_start = None

    duration_vibrations = 0
    if vibrating and vibration_start is not None:
        duration_vibrations = time.ticks_diff(time.ticks_ms(), vibration_start) / 1000


  
    if duration_vibrations >= 5:
        status = 'GEVAAR'
    elif duration_vibrations >= 3:
        status = 'RISICO'
    else:
        status = 'VEILIG'

    if not locked:
        if status in ('RISICO', 'GEVAAR'):
            locked_status = status
            locked = True
        else:
            locked_status = status
    else:
        if status == 'GEVAAR' and locked_status != 'GEVAAR':
            locked_status = 'GEVAAR'

    # Button handling: first press moves servo when yellow/red; second press resets and returns servo.
    display_status = locked_status if locked else status
    if reset_button.value() == 0 and display_status in ('RISICO', 'GEVAAR'):
        time.sleep(0.05)
        if reset_button.value() == 0:
            # wait until release to avoid bouncing
            while reset_button.value() == 0:
                time.sleep(0.05)
            if not servo_engaged:
                # first press: move servo to engaged position
                set_servo_pulse(SERVO_ENGAGED_US)
                time.sleep(0.5)
                servo_engaged = True
            else:
                # second press: move servo back and reset lock if active
                set_servo_pulse(SERVO_REST_US)
                time.sleep(0.5)
                servo_engaged = False
                if locked:
                    locked = False
                    locked_status = 'VEILIG'

    status = locked_status
    if status == 'GEVAAR':
        set_light(red)
    elif status == 'RISICO':
        set_light(yellow)
    else:
        set_light(green)

    print('tilt:', tiltwaarde, 'transitions:', transitions, 'vibrating:', vibrating, 'duration_vibrations:', round(duration_vibrations,2), 'status:', status)

    time.sleep(SAMPLE_INTERVAL)




