import network
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P4
from pimoroni import Button
import time
from ucollections import OrderedDict
from machine import Pin, UART
from umqtt.simple import MQTTClient

uart = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))
uart.init(bits=8, parity=None, stop=2)

display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, rotate=270, pen_type=PEN_P4)

WIDTH, HEIGHT = display.get_bounds()

# List of available pen colours, add more if necessary
RED = display.create_pen(209, 34, 41)
ORANGE = display.create_pen(246, 138, 30)
YELLOW = display.create_pen(255, 216, 0)
GREEN = display.create_pen(0, 121, 64)
INDIGO = display.create_pen(36, 64, 142)
VIOLET = display.create_pen(115, 41, 130)
WHITE = display.create_pen(255, 255, 255)
PINK = display.create_pen(255, 175, 200)
BLUE = display.create_pen(116, 215, 238)
BROWN = display.create_pen(97, 57, 21)
BLACK = display.create_pen(0, 0, 0)
MAGENTA = display.create_pen(255, 33, 140)
CYAN = display.create_pen(33, 177, 255)

display.update()
display.set_backlight(0.5)
display.set_font("bitmap8")

button_a = Button(12)
button_b = Button(13)
button_x = Button(14)
button_y = Button(15)

class Menu():
    options = OrderedDict([(0, "ON"), (1, "OFF"), (2, "CLOUD"), (3, "ACID"), (4, "FADE"), (5, "BLUE"), (6, "RED"), (7, "GREEN"), (8, "PRPL_RAIN")])
    selection = 0
    previous_selection = None
    
    def __init__(self):
        self.stripe_height = round(HEIGHT / len(self.options))

    def clear(self):
        display.set_pen(BLACK)
        display.clear()
        display.update()

    def render(self):
        self.clear()
        display.set_pen(WHITE)
        menu_options = list(self.options.keys())
        display.set_pen(CYAN)
        display.rectangle(0, self.stripe_height * self.selection, WIDTH, self.stripe_height)
        for option in self.options:
            if option == self.selection:
                display.set_pen(BLACK)
            else:
                display.set_pen(CYAN)
            display.text(self.options[option], 1, self.stripe_height * option + 5, 10, 3)
            
            display.update()

    def render_selection(self):
        # clear previous selection highlight box
        self.clear()
        self.render()
        display.set_pen(BLACK)
        display.rectangle(0, self.stripe_height * self.previous_selection, WIDTH, self.stripe_height)
        # move highlighted selection to new selection by rewriting old text and moving highlight box
        display.set_pen(CYAN)
        display.text(self.options[self.previous_selection], 1, (round(HEIGHT/len(self.options)) * self.previous_selection) + 5, 10, 3)
        display.rectangle(0, self.stripe_height * self.selection, WIDTH, self.stripe_height)
        # rewrite new selection in black text
        display.set_pen(BLACK)
        display.text(self.options[self.selection], 1, (round(HEIGHT/len(self.options)) * self.selection) + 5, 10, 3)
        
        
    def set_mode(self):
        display.set_pen(YELLOW)
        display.rectangle(0, self.stripe_height * self.selection, WIDTH, self.stripe_height)
        display.set_pen(BLACK)
        display.text(self.options[self.selection], 1, (round(HEIGHT/len(self.options)) * self.selection) + 5, 10, 3)
        display.update()
        time.sleep(0.5)
        display.set_pen(CYAN)
        display.rectangle(0, self.stripe_height * self.selection, WIDTH, self.stripe_height)
        display.set_pen(BLACK)
        display.text(self.options[self.selection], 1, (round(HEIGHT/len(self.options)) * self.selection) + 5, 10, 3)
        display.update()
        self.transmit_selection()
        mqtt_client.publish(mqtt_state_pub_topic, self.options[self.selection], retain=True)
        
        
    def transmit_selection(self):
        transmission = self.options[self.selection] + '\n'
        uart.write(bytearray(transmission, 'utf8'))
        
    def handle_button_press(self):
        if button_a.read():
            self.set_mode()
        elif button_b.read():
            self.previous_selection = self.selection
            self.selection -= 1
            if self.selection < 0:
                self.selection = len(self.options) - 1
            self.render_selection()
        elif button_x.read():
            self.set_mode()
        elif button_y.read():
            self.previous_selection = self.selection
            self.selection += 1
            if self.selection + 1 > len(self.options):
                self.selection = 0
            self.render_selection()

        display.update()
            
menu = Menu()
# clear()
menu.render()
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("{SSID}", "{WIFI_PASSWORD}")

while not wlan.isconnected():
    print("Connecting...")
    time.sleep(1)
print("Connected!")
PING_INTERVAL = 60
mqtt_receive_topic = "cmd/lightning_cloud/mode"
mqtt_state_pub_topic = "state/lightning_cloud/mode"
mqtt_status_topic = "state/lightning_cloud/connection_status"
mqtt_con_flag = False
pingresp_rcv_flag = True
lock = True
next_ping_time = 0

mqtt_server = '{mqtt_server_ip}'
mqtt_user = '{mqtt_user}'
mqtt_password = '{mqtt_password}'
client_id = 'lightning_pico_w'

mqtt_client = MQTTClient(
    client_id=client_id,
    server=mqtt_server,
    user=mqtt_user,
    password=mqtt_password,
    keepalive=3600
)

def mqtt_subscription_callback(topic, message):
    print (f'Topic {topic} received message {message}')  # Debug print out of what was received over MQTT
    msg = message.decode('utf-8')
    for num, opt in menu.options.items():
        if msg == opt and msg != menu.options[menu.selection]:
            menu.previous_selection = 0 if not menu.previous_selection else menu.selection
            menu.selection = num
            menu.render_selection()
            menu.set_mode()
            mqtt_client.publish(mqtt_state_pub_topic, msg, retain=True)

    print("mqtt selection", menu.selection)

mqtt_client.set_callback(mqtt_subscription_callback)
mqtt_client.set_last_will(mqtt_status_topic, "disconnected", retain=True)

def mqtt_connect():
    global next_ping_time 
    global pingresp_rcv_flag
    global mqtt_con_flag
    global lock
    while not mqtt_con_flag:
        print("trying to connect to mqtt server.")
        try:
            mqtt_client.connect()
            mqtt_client.subscribe(mqtt_receive_topic)
            mqtt_con_flag = True
            pingresp_rcv_flag = True
            next_ping_time = time.time() + PING_INTERVAL
            lock = False
            mqtt_client.publish(mqtt_status_topic, "connected", retain=True)
        except Exception as e:
            print("Error in mqtt connect: [Exception]  %s: %s" % (type(e).__name__, e))
        time.sleep(0.5)

print("Connected and subscribed")

def ping_reset():
    global next_ping_time
    next_ping_time = time.time() + PING_INTERVAL
    print("Next MQTT ping at", next_ping_time)

def ping():
    mqtt_client.ping()
    ping_reset()
    
def check():
    global next_ping_time
    global mqtt_con_flag
    global pingresp_rcv_flag
    if (time.time() >= next_ping_time):
        ping()
#         print("FUCK")
#         if not pingresp_rcv_flag:
#             mqtt_con_flag = False
#             print("We have not received PINGRESP so broker disconnected")
#         else:
#             print("MQTT ping at", time.time())
#             ping()
#             ping_resp_rcv_flag = False
#     res = mqtt_client.check_msg()
#     if(res == b"PINGRESP"):
#         pingresp_rcv_flag = True
#         print("PINGRESP")
#     else:
#         ping()
        res = mqtt_client.check_msg()
#         if(res == b"PINGRESP"):
#             pingresp_rcv_flag = True
#             print("PINGRESP")
    mqtt_client.check_msg()
    

while True:
    mqtt_connect()
    try:
        check()
    except Exception as e:
        print("Error in Mqtt check message: [Exception] %s: %s" % (type(e).__name__, e))
        print("MQTT disconnected due to network problem")
        lock = True
        mqtt_con_flag = False
    menu.handle_button_press()
    time.sleep(0.1)
