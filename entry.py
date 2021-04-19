#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os

from sbtPythonCan.read_from_mqtt import MessageReceiver, RxFrame

homedir = 'epaper/e-Paper/RaspberryPi_JetsonNano/python/'
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 
homedir+'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 
homedir+'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
import threading
import RPi.GPIO as GPIO
from waveshare_epd import epd3in7
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

logging.basicConfig(level=logging.DEBUG)

# variables
epd = epd3in7.EPD()
updatingPins=True
updatingMain=True
updatingData=True
RESET_SCREEN_PIN = 27  # board 13, BCM 27
NEXT_SCREEN_PIN  = 22  # board 15, BCM 22
SCREEN_1 = 0
SCREEN_2 = 1
currentScreen = SCREEN_1
w = epd3in7.EPD_HEIGHT # 480
h = epd3in7.EPD_WIDTH  # 280
DRAW_LEFT_COL = 0
DRAW_RIGHT_COL= 1
font24 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 28)
rowsDescriptions = [
    ['voltage','current','battery temp'],
    ['height back','height front','speed gps','speed pitot']
]
tableLinesXY = [

    [
    [(0  , 1/3*h),(w  , 1/3*h)],
    [(0  , 2/3*h),(w  , 2/3*h)],
    [(w*2/5, 0  ),(w*2/5, h  )]    # vertical line
    ],

    [
    [(0  , 1/4*h),(w  , 1/4*h)],
    [(0  , 2/4*h),(w  , 2/4*h)],
    [(0  , 3/4*h),(w  , 3/4*h)],
    [(w*2/5, 0  ),(w*2/5, h  )]    # vertical line
    ]
]
tmp = [i for i in range(5)]

# draw functions
def drawTable(canvas):
    for xy in tableLinesXY[currentScreen]:
        canvas.line(xy, width=2, joint=None)

def drawData(canvas, drawMode):
    if not (currentScreen == SCREEN_1 or currentScreen == SCREEN_2):
        return

    offset = -1
    rows = -1
    if currentScreen == SCREEN_1:    # 3
        offset = 35
        rows = 3
    elif currentScreen == SCREEN_2:  # 4
        offset = 14
        rows = 4

    if drawMode == DRAW_LEFT_COL:
        for i in range(rows):
                canvas.text((20  , i/rows*h+offset), rowsDescriptions[currentScreen][i], font = font24, fill = 0)
    elif drawMode == DRAW_RIGHT_COL:
        for i in range(rows):
                canvas.text((w/2+20, i/rows*h+offset), str(tmp[i]), font = font24, fill = 0)

# display functions

def display(image, delay=2):
    epd.display_4Gray(epd.getbuffer_4Gray(image))
    logging.info(f"DISPLAYED, NOW WAIT {delay}s")
    time.sleep(delay)
    logging.info("WAIT ENDED")

def displayData(image):
    epd.display_1Gray(epd.getbuffer(image))

# thread functions

def updateData():
    while(updatingData):
        for i in range(5):
            tmp[i] += .1234
        time.sleep(.4)

def updatePins():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RESET_SCREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(NEXT_SCREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    while(updatingPins):
        if GPIO.input(RESET_SCREEN_PIN): # board 13, BCM 27
            logging.info("RESET_SCREEN_PIN - resetting partial")
            reset(1,3)

        if GPIO.input(NEXT_SCREEN_PIN): # board 15, BCM 22
            logging.info("NEXT_SCREEN_PIN")
            global currentScreen
            if currentScreen == SCREEN_1:
                currentScreen = SCREEN_2
            elif currentScreen == SCREEN_2:
                currentScreen = SCREEN_1
            swapScreen()
            time.sleep(5)

        logging.info("handling")
        time.sleep(.25)

# utility functions

def reset(mode, delay=0):
    epd.init(mode)
    epd.Clear(0xFF, mode)
    time.sleep(delay)

def swapScreen():
    image = Image.new('L', (epd.height, epd.width), 0xFF)  # 0xFF: clear the frame
    canvas = ImageDraw.Draw(image)

    drawTable(canvas)
    drawData(canvas, DRAW_LEFT_COL)
    display(image)


def quitEpaper():
    time.sleep(1)
    logging.info("Clear...")
    reset(0)
    reset(1)
    logging.info("Goto Sleep...")
    epd.sleep()

    epd3in7.epdconfig.module_exit()
    exit()


def restartEpaper():
    global currentScreen
    try:
        logging.info("init and Clear, NOW WAIT")
        time.sleep(2)
        reset(0, .1)
        reset(0, .5)
        
        currentScreen = SCREEN_2
        # user code start
        swapScreen()
        
        reset(1, .2)
        # partial display
        while(updatingMain):
            dataImage = Image.new('L', (epd.height, epd.width), 0xFF)  # 0xFF: clear the frame
            dataCanvas = ImageDraw.Draw(dataImage)
            drawData(dataCanvas, DRAW_RIGHT_COL)
            displayData(dataImage)
            time.sleep(.25)
        
        logging.info("--------end--------")
        quitEpaper()
        
    except IOError as e:
        logging.info(e)
        quitEpaper()
        
    except KeyboardInterrupt:    
        logging.info("ctrl + c:")
        updatingPins=False
        updatingData=False
        # quitEpaper()

# MAIN
# declare threads
pinUpdater = threading.Thread(target=updatePins, args=())
dataUpdater = threading.Thread(target=updateData, args=())
mainUpdater = threading.Thread(target=restartEpaper, args=())

# run threads
pinUpdater.start()
dataUpdater.start()
mainUpdater.start()

# join threads
pinUpdater.join()
mainUpdater.join()
dataUpdater.join()

