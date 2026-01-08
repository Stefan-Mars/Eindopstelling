from machine import Pin, PWM
import time

# Configuratie (pinnen en timing)
TILT_PIN = 15
RED_PIN = 38
YELLOW_PIN = 37
GREEN_PIN = 36
RESET_PIN = 0
SERVO_PIN = 18

SAMPLE_INTERVAL = 0.1
WINDOW_SECONDS = 1.0
VIBRATION_TRANSITIONS_THRESHOLD = 1

# Pulslengtes in microseconden voor standaardservos
SERVO_MIN_US = 500
SERVO_MAX_US = 2400
SERVO_REST_US = SERVO_MIN_US
SERVO_ENGAGED_US = SERVO_MAX_US


# Hardware init
tilt = Pin(TILT_PIN, Pin.IN, Pin.PULL_UP)
red = Pin(RED_PIN, Pin.OUT)
yellow = Pin(YELLOW_PIN, Pin.OUT)
green = Pin(GREEN_PIN, Pin.OUT)
reset_button = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)
pwm_servo = PWM(Pin(SERVO_PIN), freq=50)

# Buffer voor trillingsdetectie (Hoeveel van de vorige trillingen hij meet)
BUFFER_SIZE = max(2, int(WINDOW_SECONDS / SAMPLE_INTERVAL))
tilt_buffer = [tilt.value()] * BUFFER_SIZE
buffer_index = 0

# State
vibrating = False
vibration_start = None
locked = False
locked_status = 'VEILIG'
servo_engaged = False

# Knop debounce state. (Dit zorgt ervoor dat de knop niet 2 keer wordt ingedrukt als je het maar 1 keer doet)
last_button_state = reset_button.value()
last_button_time = time.ticks_ms()
button_debounce_ms = 50
last_action_time = 0



def set_servo_pulse(us):
    # Zet pulslengte in microseconden. Servo gebruikt pulslengte. ESP32 gebruikt microseconden
    duty = int(us * 65535 / 20000)
    pwm_servo.duty_u16(duty)




def set_light(active):
    red.off()
    yellow.off()
    green.off()
    active.on()


def update_buffer():
    global buffer_index
    val = tilt.value()
    tilt_buffer[buffer_index] = val
    buffer_index = (buffer_index + 1) % BUFFER_SIZE


def compute_transitions():
    # Bereken aantal overgangen tussen opeenvolgende trillingen in de buffer (Als er een trilling is is het dan 010101 en dat berekent ie)
    return sum(tilt_buffer[i] != tilt_buffer[i-1] for i in range(1, BUFFER_SIZE))


def update_vibration_state(transitions):
    global vibrating, vibration_start
    if transitions > VIBRATION_TRANSITIONS_THRESHOLD:
        if not vibrating:
            vibrating = True
            vibration_start = time.ticks_ms()
    else:
        if vibrating:
            vibrating = False
            vibration_start = None


def get_vibration_duration():
    if vibrating and vibration_start is not None:
        return time.ticks_diff(time.ticks_ms(), vibration_start) / 1000
    return 0


def handle_button_edge(display_status):
    # Veranderd de status als je op de knop drukt
    global last_button_state, last_button_time, last_action_time, servo_engaged, locked, locked_status
    now = time.ticks_ms()
    state = reset_button.value()
    if state != last_button_state:
        last_button_time = now
        last_button_state = state

    if time.ticks_diff(now, last_button_time) >= button_debounce_ms:
        # detecteer druk-rand (hoog->laag)
        if state == 0 and time.ticks_diff(now, last_action_time) > 200:
            if display_status in ('RISICO', 'GEVAAR'):
                if not servo_engaged:
                    set_servo_pulse(SERVO_ENGAGED_US)
                    time.sleep(0.5)
                    servo_engaged = True
                else:
                    set_servo_pulse(SERVO_REST_US)
                    time.sleep(0.5)
                    servo_engaged = False
                    if locked:
                        locked = False
                        locked_status = 'VEILIG'
                last_action_time = now


# Start in rustpositie
set_servo_pulse(SERVO_REST_US)


# Hoofdloop
try:
    while True:
        update_buffer()
        transitions = compute_transitions()
        update_vibration_state(transitions)
        duration_vibrations = get_vibration_duration()

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

        display_status = locked_status if locked else status
        handle_button_edge(display_status)

        status_to_display = locked_status
        if status_to_display == 'GEVAAR':
            set_light(red)
        elif status_to_display == 'RISICO':
            set_light(yellow)
        else:
            set_light(green)

        print('tilt:', tilt_buffer[(buffer_index-1)%BUFFER_SIZE],
              'transitions:', transitions,
              'vibrating:', vibrating,
              'duration_vibrations:', round(duration_vibrations,2),
              'status:', status_to_display)

        time.sleep(SAMPLE_INTERVAL)
except Exception:
    # Probeer servo in veilige positie te zetten
    try:
        set_servo_pulse(SERVO_REST_US)
    except Exception:
        pass
    raise




