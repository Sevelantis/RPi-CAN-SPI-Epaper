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
pausingMain=False
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
rowsUnits = [
    [' [V]',' [A]',' [°C]'],
    [' [m]',' [m]',' [m/s]',' [m/s]']
]
tableLinesXY = [

    [
    [(0  , 1/3*h),(w  , 1/3*h)],
    [(0  , 2/3*h),(w  , 2/3*h)],
    [(w*1/2, 0  ),(w*1/2, h  )]    # vertical line
    ],

    [
    [(0  , 1/4*h),(w  , 1/4*h)],
    [(0  , 2/4*h),(w  , 2/4*h)],
    [(0  , 3/4*h),(w  , 3/4*h)],
    [(w*1/2, 0  ),(w*1/2, h  )]    # vertical line
    ]
]
zupa = dict()
warzywa = [
    ['-1','-1','-1'],
    ['-1','-1','-1','-1']
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
        offset = 30
        rows = 3
    elif currentScreen == SCREEN_2:  # 4
        offset = 16
        rows = 4

    if drawMode == DRAW_LEFT_COL:
        for i in range(rows):
            canvas.text((20  , i/rows*h+offset), rowsDescriptions[currentScreen][i], font = font24, fill = 0)
    elif drawMode == DRAW_RIGHT_COL:
        for i in range(rows):
            canvas.text((w/2+60, i/rows*h+offset), warzywa[currentScreen][i] + rowsUnits[currentScreen][i], font = font24, fill = 0)

# display functions

def display(image, delay=2):
    epd.display_4Gray(epd.getbuffer_4Gray(image))
    logging.info(f"DISPLAYED, NOW WAIT {delay}s")
    time.sleep(delay)
    logging.info("WAIT ENDED")

def displayData(image):
    epd.display_1Gray(epd.getbuffer(image))

# thread functions
def displayer_on_frame(frame: RxFrame):
    zupa.update({frame.frame_type: frame.value})

# program generated data
# def updateData():
#     time.sleep(10) # wait for epaper init
#     while(updatingData):
#         for i in range(5):
#             tmp[i] += .1234
#         time.sleep(.4)

# data from server
def updateData():
    global zupa
    time.sleep(10) # wait for epaper init
    receiver = MessageReceiver(displayer_on_frame)
    while updatingData:
        for key, value in zupa.items():
            for i in range(2):
                cols = -1
                if i == 0:
                    cols = 3
                elif i == 1:
                    cols = 4
                
                for j in range(cols):
                    if key == rowsDescriptions[i][j]:
                        warzywa[i][j] = converter(str(value))
                        # logging.info("\t{} -> {}".format(key, value))

        # data is properly read from the server:
        # for i in range(3):
        #     logging.info(f'{i}->\t{warzywa[0][i]}')
        # for i in range(4):
        #     logging.info(f'{i}->\t{warzywa[1][i]}')
        # logging.info("-----")
        time.sleep(.66)

def updatePins():
    time.sleep(10) # wait for epaper init
    global updatingMain, pausingMain, mainUpdater, currentScreen
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RESET_SCREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(NEXT_SCREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    while(updatingPins):
        if GPIO.input(RESET_SCREEN_PIN): # board 13, BCM 27
            logging.info("RESET_SCREEN_PIN---------------------")

            pausingMain=True
            resetEpaper()
            time.sleep(2)
            pausingMain=False
                
            logging.info("RESET_SCREEN_PIN-------RESTARTED----")

        if GPIO.input(NEXT_SCREEN_PIN): # board 15, BCM 22
            logging.info("NEXT_SCREEN_PIN---------------------")
            pausingMain=True

            if currentScreen == SCREEN_1:
                currentScreen = SCREEN_2
            elif currentScreen == SCREEN_2:
                currentScreen = SCREEN_1

            pausingMain=False
            time.sleep(.75)
            logging.info("SCREEN SWAPPED")

        logging.info("handling pins")
        time.sleep(.75)
    logging.info("updatePins - EXIT")

# utility functions

def updateScreen():
    img = Image.new('L', (epd.height, epd.width), 0xFF)  # 0xFF: clear the frame
    canvas = ImageDraw.Draw(img)
    time.sleep(.05)
    drawTable(canvas)
    time.sleep(.05)
    drawData(canvas, DRAW_RIGHT_COL)
    time.sleep(.05)
    drawData(canvas, DRAW_LEFT_COL)
    time.sleep(.05)
    displayData(img)

def reset(mode, delay=0):
    epd.init(mode)
    epd.Clear(0xFF, mode)
    time.sleep(delay)

def resetEpaper():
    global epd
    epd = epd3in7.EPD()

    logging.info("init and Clear, NOW WAIT")
    time.sleep(.2)
    reset(0, 1)
    reset(0, 2)
    reset(1, 1)
    reset(1, 2)
    # update screen before loop 
    updateScreen()

def quitEpaper():
    time.sleep(1)
    logging.info("Clear...")
    reset(0)
    reset(1)
    logging.info("Goto Sleep...")
    epd.sleep()

    epd3in7.epdconfig.module_exit()
    exit()

def converter(variable):
    my_float_number=float(variable)
    formated_float_number = '{:.2f}'.format(my_float_number)
    x = repr(formated_float_number).replace('\'','')
    return x

def runEpaper():
    global currentScreen
    try:
        # reset current screen data...
        resetEpaper()
        # wait while its transmitting data...
        time.sleep(2)
        # partial display
        while(updatingMain):
            if pausingMain:    
                logging.info("robotnicy stop---cos sie dzieje---")
            else:
                updateScreen()
            time.sleep(.2)
        
        logging.info("end")
        quitEpaper()
        
    except IOError as e:
        logging.info(e)
        quitEpaper()
        
    except KeyboardInterrupt:
        global updatingPins, updatingData
        logging.info("ctrl + c:")
        updatingPins=False
        updatingData=False
        quitEpaper()

# MAIN
if __name__ == '__main__':
    # declare threads
    pinUpdater = threading.Thread(target=updatePins, args=())
    dataUpdater = threading.Thread(target=updateData, args=())
    mainUpdater = threading.Thread(target=runEpaper, args=())

    # run threads
    pinUpdater.start()
    dataUpdater.start()
    mainUpdater.start()

    # join threads
    mainUpdater.join()
    pinUpdater.join()
    dataUpdater.join()

