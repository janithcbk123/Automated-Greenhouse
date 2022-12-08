import time
import pyrebase
import Adafruit_DHT
import spidev
import RPi.GPIO as GPIO
import smbus
import csv
from datetime import datetime

# configures firebase

firebaseConfig = {
    "apiKey": "AIzaSyA1cZhgLy_rE6I23zvKhg4Gy3LpfJJJ6tk",
    "authDomain": "greenhouseautomation-8af0f.firebaseapp.com",
    "databaseURL": "https://greenhouseautomation-8af0f-default-rtdb.firebaseio.com",
    "storageBucket": "greenhouseautomation-8af0f.appspot.com"
}

firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()

# configures the smbus module for the analog to digital convertor

bus = smbus.SMBus(1)
address = 0x48

# configures output pins and initializes them
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

redLED = 23
blueLED = 24

GPIO.setup(17, GPIO.OUT)
GPIO.output(17, False)
GPIO.setup(27, GPIO.OUT)
GPIO.output(27, False)
GPIO.setup(22, GPIO.OUT)
GPIO.output(22, False)
GPIO.setup(redLED, GPIO.OUT)
GPIO.setup(blueLED, GPIO.OUT)

red_pwm = GPIO.PWM(redLED, 1000)
blue_pwm = GPIO.PWM(blueLED, 1000)


# read function used for the analog to digital convertor
def read(control):
    write = bus.write_byte(address, control)  
    read = bus.read_byte(address)
    return read


# function to return temperature and humidity values from sensor
def temp_humid_sensor():
    DHT_SENSOR = Adafruit_DHT.DHT11
    DHT_PIN = 4

    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
    if humidity is not None and temperature is not None:
        print("Temp={0:0.1f}C Humidity={1:0.1f}%".format(temperature, humidity))
    else:
        print("DHT sensor failure.")
        temperature = 29
        humidity = 91
    return temperature, humidity


# function to return light and moisture values from sensor through ADC
def light_moisture_sensor():
    unused1 = read(0x40)
    moisture_raw = read(0x41)
    unused2 = read(0x42)
    light_raw = read(0x43)

    moisture = (moisture_raw / float(255) * 100)
    moisture = round(moisture, 2)

    light = (light_raw / float(255) * 1000)
    light = round(light, 2)

    return light, moisture


# function to update the firebase with the latest sensor values
def update_database(humidity, light, moisture, temperature):
    db.child("IOTGreenhouse").update({"humidity": humidity})
    db.child("IOTGreenhouse").update({"luminosity": light})
    db.child("IOTGreenhouse").update({"moisture": moisture})
    db.child("IOTGreenhouse").update({"temperature": temperature})


# function to open or close fan
def fan(state):
    try:
        GPIO.output(17, state)
    except:
        print("error")
        pass


# function to start or stop sprinkling
def sprinkle(state):
    try:
        GPIO.output(27, state)
    except:
        print("error")
        pass


# function to start or stop dripping
def drip(state):
    try:
        GPIO.output(22, state)
    except:
        print("error")
        pass


# function to filter quotes from string and then convert to int
def convert_int(string_unfiltered):
    string_filtered = string_unfiltered.replace('"', '')
    integer = int(string_filtered)
    return integer


# function for saving data to a local csv file
def save_to_csv(temp, humid, light, moist):
    now = datetime.now()
    current_day = now.strftime("%d/%m/%Y")
    current_time = now.strftime("%H:%M:%S")

    with open('data.csv', 'a', newline='') as file:
        fieldnames = ['Date', 'Time', 'Temperature', 'Humidity', 'Light', 'Moisture']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        # writer.writeheader()
        writer.writerow(
            {'Date': current_day, 'Time': current_time, 'Temperature': temp, 'Humidity': humid, 'Light': light,
             'Moisture': moist})


# main code starts here


try:
    # starts the red and blue LEDs
    red_pwm.start(50)
    blue_pwm.start(50)
    while True:
        # gets new data from sensors and uploads them to firbase and save locally
        temp, humid = temp_humid_sensor()
        light_level, moist = light_moisture_sensor()
        
        save_to_csv(temp, humid, light_level, moist)
        update_database(humid, light_level, moist, temp)

        # adjusts dutycycle of red and blue PWM according to instructions
        dutycycle = convert_int(db.child("IOTGreenhouse").child("led intensity").get().val())

        if dutycycle<50:
            reddutycycle = 100
            bluedutycycle = 25
        elif dutycycle == 50:
            reddutycycle = 100
            bluedutycycle = 100
        else:
            reddutycycle = 25
            bluedutycycle = 100

        red_pwm.ChangeDutyCycle(reddutycycle)
        blue_pwm.ChangeDutyCycle(bluedutycycle)

        # checks and switches the mode of operation
        automatic = db.child("IOTGreenhouse").child("automatic").get().val()

        if automatic == 'true':
            # code for automatic mode starts here
            # retrieves the acceptable parameters from firebase database
            temp_max = convert_int(db.child("IOTGreenhouse").child("temp max").get().val())
            temp_min = convert_int(db.child("IOTGreenhouse").child("temp min").get().val())
            humid_max = convert_int(db.child("IOTGreenhouse").child("humid max").get().val())
            humid_min = convert_int(db.child("IOTGreenhouse").child("humid min").get().val())
            moist_max = convert_int(db.child("IOTGreenhouse").child("moist max").get().val())
            moist_min = convert_int(db.child("IOTGreenhouse").child("moist min").get().val())

            # opens and closes relays depending on conditions
            if temp > temp_max:
                fan(True)
            elif temp < temp_min:
                fan(False)

            if humid > humid_max:
                sprinkle(True)
            elif humid < humid_min:
                sprinkle(False)

            if moist < moist_min:
                drip(True)
            elif moist > moist_max:
                drip(False)
        else:
            # code for manual mode starts here
            # retrieves instructions for relays from firebase
            turn_on_dripping = db.child("IOTGreenhouse").child("turn on dripping").get().val()
            turn_on_sprinkling = db.child("IOTGreenhouse").child("turn on sprinkling").get().val()
            turn_on_fan = db.child("IOTGreenhouse").child("turn on fan").get().val()

            # opens or closes relays according to instructions
            if turn_on_dripping == 'true':
                drip(True)
            else:
                drip(False)
            if turn_on_sprinkling == 'true':
                sprinkle(True)
            else:
                sprinkle(False)
            if turn_on_fan == 'true':
                fan(True)
            else:
                fan(False)

except KeyboardInterrupt:
    # breaks the loop and moves on to the cleanup of outputs
    print("Interrupted by user")

finally:
    # cleans up outputs and terminates the lighting
    red_pwm.stop()
    blue_pwm.stop()
    GPIO.cleanup()
