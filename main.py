from machine import Pin,SPI,PWM
import framebuf
import time
import os
import ujson
import network
import requests
import math
import gc

BL = 13
DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9

# ================== INI ================== 
    # wifi
ssid = 'your ssid'
password = 'your awesome wifi password'

    # N2YO API key: get it here after account creation https://www.n2yo.com/login/edit/
api_key = "XXXXXX-XXXXXX-XXXXXX-XXXXXX"
   
    # location where you want to check the satelites above
base_settings = "47.50;19.04;0" # lat;lng;elevation first ever run values. Also the last ones as I never finished the settings view where you can set this up

view = 0 # it starts here. 0 - satelites view, 1 - settings view

# ================== INI END ================== 

settings_file = "settings.txt" # at first run this will be created with base_settings
settings = "" # will be populated either with base_settings at first run or settings.txt contents every time after that
api_url = "https://api.n2yo.com/rest/v1/satellite/above"


above_in_view = 0 # the satelite in view

step_time = 100 # left and right step speed between satelites in ms
latlng_step_time = 200 # settings number step time needs to be fast to be used
api_refresh_time = 40000 # you have 100 per hour limit so 36000 is the absolute minimum. Do not forget every restart is an API call too, keep that in mind when debuging.

selected_setting = 0 # 0 - lat, 1 - lng, 2 - alt

# screen setup (this code came with the LCD)
class LCD_1inch3(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 240
        self.height = 240
        
        self.cs = Pin(CS,Pin.OUT)
        self.rst = Pin(RST,Pin.OUT)
        
        self.cs(1)
        self.spi = SPI(1)
        self.spi = SPI(1,1000_000)
        self.spi = SPI(1,100000_000,polarity=0, phase=0,sck=Pin(SCK),mosi=Pin(MOSI),miso=None)
        self.dc = Pin(DC,Pin.OUT)
        self.dc(1)
        self.buffer = bytearray(self.height * self.width * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)
        self.init_display()
        
        self.red   =   0x07E0
        self.green =   0x001f
        self.blue  =   0xf800
        self.white =   0xffff
        
    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)
        
    def init_display(self):
        """Initialize dispaly"""  
        self.rst(1)
        self.rst(0)
        self.rst(1)
        
        self.write_cmd(0x36)
        self.write_data(0x70)

        self.write_cmd(0x3A) 
        self.write_data(0x05)

        self.write_cmd(0xB2)
        self.write_data(0x0C)
        self.write_data(0x0C)
        self.write_data(0x00)
        self.write_data(0x33)
        self.write_data(0x33)

        self.write_cmd(0xB7)
        self.write_data(0x35) 

        self.write_cmd(0xBB)
        self.write_data(0x19)

        self.write_cmd(0xC0)
        self.write_data(0x2C)

        self.write_cmd(0xC2)
        self.write_data(0x01)

        self.write_cmd(0xC3)
        self.write_data(0x12)   

        self.write_cmd(0xC4)
        self.write_data(0x20)

        self.write_cmd(0xC6)
        self.write_data(0x0F) 

        self.write_cmd(0xD0)
        self.write_data(0xA4)
        self.write_data(0xA1)

        self.write_cmd(0xE0)
        self.write_data(0xD0)
        self.write_data(0x04)
        self.write_data(0x0D)
        self.write_data(0x11)
        self.write_data(0x13)
        self.write_data(0x2B)
        self.write_data(0x3F)
        self.write_data(0x54)
        self.write_data(0x4C)
        self.write_data(0x18)
        self.write_data(0x0D)
        self.write_data(0x0B)
        self.write_data(0x1F)
        self.write_data(0x23)

        self.write_cmd(0xE1)
        self.write_data(0xD0)
        self.write_data(0x04)
        self.write_data(0x0C)
        self.write_data(0x11)
        self.write_data(0x13)
        self.write_data(0x2C)
        self.write_data(0x3F)
        self.write_data(0x44)
        self.write_data(0x51)
        self.write_data(0x2F)
        self.write_data(0x1F)
        self.write_data(0x1F)
        self.write_data(0x20)
        self.write_data(0x23)
        
        self.write_cmd(0x21)

        self.write_cmd(0x11)

        self.write_cmd(0x29)

    def show(self):
        self.write_cmd(0x2A)
        self.write_data(0x00)
        self.write_data(0x00)
        self.write_data(0x00)
        self.write_data(0xef)
        
        self.write_cmd(0x2B)
        self.write_data(0x00)
        self.write_data(0x00)
        self.write_data(0x00)
        self.write_data(0xEF)
        
        self.write_cmd(0x2C)
        
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(self.buffer)
        self.cs(1)
  

   
# thanks tonygo2 https://www.instructables.com/Computer-Graphics-101-With-Pi-Pico-and-Colour-Disp/
cmap = ['00000000000000000000000000000000000', #Space
        '00100001000010000100001000000000100', #!
        '01010010100000000000000000000000000', #"
        '01010010101101100000110110101001010', ##
        '00100011111000001110000011111000100', #$
        '11001110010001000100010001001110011', #%
        '01000101001010001000101011001001101', #&
        '10000100001000000000000000000000000', #'
        '00100010001000010000100000100000100', #(
        '00100000100000100001000010001000100', #)
        '00000001001010101110101010010000000', #*
        '00000001000010011111001000010000000', #+
        '000000000000000000000000000000110000100010000', #,
        '00000000000000011111000000000000000', #-
        '00000000000000000000000001100011000', #.
        '00001000010001000100010001000010000', #/
        '01110100011000110101100011000101110', #0
        '00100011000010000100001000010001110', #1
        '01110100010000101110100001000011111', #2
        '01110100010000101110000011000101110', #3
        '00010001100101011111000100001000010', #4
        '11111100001111000001000011000101110', #5
        '01110100001000011110100011000101110', #6
        '11111000010001000100010001000010000', #7
        '01110100011000101110100011000101110', #8
        '01110100011000101111000010000101110', #9
        '00000011000110000000011000110000000', #:
        '01100011000000001100011000010001000', #;
        '00010001000100010000010000010000010', #<
        '00000000001111100000111110000000000', #=
        '01000001000001000001000100010001000', #>
        '01100100100001000100001000000000100', #?
        '01110100010000101101101011010101110', #@
        '00100010101000110001111111000110001', #A
        '11110010010100111110010010100111110', #B
        '01110100011000010000100001000101110', #C
        '11110010010100101001010010100111110', #D
        '11111100001000011100100001000011111', #E
        '11111100001000011100100001000010000', #F
        '01110100011000010111100011000101110', #G
        '10001100011000111111100011000110001', #H
        '01110001000010000100001000010001110', #I
        '00111000100001000010000101001001100', #J
        '10001100101010011000101001001010001', #K
        '10000100001000010000100001000011111', #L
        '10001110111010110101100011000110001', #M
        '10001110011010110011100011000110001', #N
        '01110100011000110001100011000101110', #O
        '11110100011000111110100001000010000', #P
        '01110100011000110001101011001001101', #Q
        '11110100011000111110101001001010001', #R
        '01110100011000001110000011000101110', #S
        '11111001000010000100001000010000100', #T
        '10001100011000110001100011000101110', #U
        '10001100011000101010010100010000100', #V
        '10001100011000110101101011101110001', #W
        '10001100010101000100010101000110001', #X
        '10001100010101000100001000010000100', #Y
        '11111000010001000100010001000011111', #Z
        '01110010000100001000010000100001110', #[
        '10000100000100000100000100000100001', #\
        '00111000010000100001000010000100111', #]
        '00100010101000100000000000000000000', #^
        '00000000000000000000000000000011111', #_
        '11000110001000001000000000000000000', #`
        '00000000000111000001011111000101110', #a
        '10000100001011011001100011100110110', #b
        '00000000000011101000010000100000111', #c
        '00001000010110110011100011001101101', #d
        '00000000000111010001111111000001110', #e
        '00110010010100011110010000100001000', #f
        '000000000001110100011000110001011110000101110', #g
        '10000100001011011001100011000110001', #h
        '00100000000110000100001000010001110', #i
        '0001000000001100001000010000101001001100', #j
        '10000100001001010100110001010010010', #k
        '01100001000010000100001000010001110', #l
        '00000000001101010101101011010110101', #m
        '00000000001011011001100011000110001', #n
        '00000000000111010001100011000101110', #o
        '000000000001110100011000110001111101000010000', #p
        '000000000001110100011000110001011110000100001', #q
        '00000000001011011001100001000010000', #r
        '00000000000111110000011100000111110', #s
        '00100001000111100100001000010000111', #t
        '00000000001000110001100011001101101', #u
        '00000000001000110001100010101000100', #v
        '00000000001000110001101011010101010', #w
        '00000000001000101010001000101010001', #x
        '000000000010001100011000110001011110000101110', #y
        '00000000001111100010001000100011111', #z
        '00010001000010001000001000010000010', #{
        '00100001000010000000001000010000100', #|
        '01000001000010000010001000010001000', #}
        '01000101010001000000000000000000000' #}~
]
# thanks tonygo2 https://www.instructables.com/Computer-Graphics-101-With-Pi-Pico-and-Colour-Disp/
def printchar(letter,xpos,ypos,size,c,lcd):
    origin = xpos
    charval = ord(letter)
    #print(charval)
    index = charval-32 #start code, 32 or space
    #print(index)
    character = cmap[index] #this is our char...
    rows = [character[i:i+5] for i in range(0,len(character),5)]
    #print(rows)
    for row in rows:
        #print(row)
        for bit in row:
            #print(bit)
            if bit == '1':
                lcd.pixel(xpos,ypos,c)
                if size==2:
                    lcd.pixel(xpos,ypos+1,c)
                    lcd.pixel(xpos+1,ypos,c)
                    lcd.pixel(xpos+1,ypos+1,c)
                if size == 3:                    
                    lcd.pixel(xpos,ypos+1,c)
                    lcd.pixel(xpos,ypos+2,c)
                    lcd.pixel(xpos+1,ypos,c)
                    lcd.pixel(xpos+1,ypos+1,c)
                    lcd.pixel(xpos+1,ypos+2,c)
                    lcd.pixel(xpos+2,ypos,c)
                    lcd.pixel(xpos+2,ypos+1,c)
                    lcd.pixel(xpos+2,ypos+2,c)                  
            xpos+=size
        xpos=origin
        ypos+=size
# thanks tonygo2 https://www.instructables.com/Computer-Graphics-101-With-Pi-Pico-and-Colour-Disp/
def delchar(xpos,ypos,size,lcd):
    if size == 1:
        charwidth = 5
        charheight = 9
    if size == 2:
        charwidth = 10
        charheight = 18
    if size == 3:
        charwidth = 15
        charheight = 27
    c=colour(40,40,40)
    lcd.fill_rect(xpos,ypos,charwidth,charheight,0) #xywh
# thanks tonygo2 https://www.instructables.com/Computer-Graphics-101-With-Pi-Pico-and-Colour-Disp/
def printstring(string,xpos,ypos,size,c,lcd):
    if size == 1:
        spacing = 8
    if size == 2:
        spacing = 14
    if size == 3:
        spacing = 18
    for i in string:
        printchar(i,xpos,ypos,size,c,lcd)
        xpos+=spacing

 # thanks tonygo2 https://www.instructables.com/Computer-Graphics-101-With-Pi-Pico-and-Colour-Disp/
def color(R,G,B): 
    mix1 = ((R&0xF8)*256) + ((G&0xFC)*8) + ((B&0xF8)>>3)
    return (mix1 & 0xFF) *256 + int((mix1 & 0xFF00) /256)


# from here everything is written by me. It is free and open source.
def draw_icon(mode,x, y,LCD, main_color):
    # 0 - cog, 1 - refresh
    icons = [[[1,9],[1,10],[2,8],[2,9],[2,10],[2,15],[3,3],[3,4],[3,8],[3,9],[3,10],[3,11],[3,15],[3,16],[4,3],[4,4],[4,5],[4,6],[4,7],[4,8],[4,9],[4,10],[4,11],[4,12],[4,13],[4,14],[4,15],[4,16],[5,3],[5,4],[5,5],[5,6],[5,7],[5,12],[5,13],[5,14],[5,15],[6,4],[6,5],[6,6],[6,13],[6,14],[6,15],[7,4],[7,5],[7,14],[7,15],[7,16],[8,3],[8,4],[8,5],[8,14],[8,15],[8,16],[8,18],[9,1],[9,2],[9,3],[9,4],[9,15],[9,16],[9,17],[9,18],[10,1],[10,2],[10,3],[10,4],[10,15],[10,16],[10,17],[10,18],[11,1],[11,3],[11,4],[11,5],[11,14],[11,15],[11,16],[12,3],[12,4],[12,5],[12,14],[12,15],[12,16],[13,4],[13,5],[13,6],[13,13],[13,14],[13,15],[14,4],[14,5],[14,6],[14,7],[14,12],[14,13],[14,14],[14,15],[14,16],[15,3],[15,4],[15,5],[15,6],[15,7],[15,8],[15,9],[15,10],[15,11],[15,12],[15,13],[15,14],[15,15],[15,16],[16,3],[16,4],[16,8],[16,9],[16,10],[16,11],[16,12],[16,15],[16,16],[17,4],[17,9],[17,10],[17,11],[18,9],[18,10]],
            [[1,6],[1,7],[1,8],[1,9],[1,10],[1,11],[1,12],[1,13],[2,4],[2,5],[2,6],[2,7],[2,8],[2,9],[2,10],[2,11],[2,12],[2,13],[2,14],[2,15],[3,3],[3,4],[3,5],[3,6],[3,7],[3,12],[3,13],[3,14],[3,15],[3,16],[4,2],[4,3],[4,4],[4,5],[4,14],[4,15],[4,16],[4,17],[5,2],[5,3],[5,4],[5,15],[5,16],[5,17],[6,1],[6,2],[6,3],[6,16],[6,17],[6,18],[7,1],[7,2],[7,3],[7,16],[7,17],[7,18],[8,1],[8,2],[8,17],[8,18],[9,1],[9,2],[9,17],[9,18],[10,1],[10,2],[10,17],[10,18],[11,1],[11,2],[11,17],[11,18],[12,1],[12,2],[12,17],[12,18],[13,1],[13,2],[13,3],[13,16],[13,17],[13,18],[14,2],[14,3],[14,6],[14,15],[14,16],[14,17],[15,2],[15,3],[15,4],[15,5],[15,6],[15,14],[15,15],[15,16],[15,17],[16,3],[16,4],[16,5],[16,6],[16,13],[16,14],[16,15],[16,16],[17,3],[17,4],[17,5],[17,6],[17,12],[17,13],[17,14],[17,15],[18,2],[18,6],[18,12],[18,13],]]

    for pixel in icons[mode]:
        LCD.pixel(x + pixel[0], y + pixel[1], main_color)

def write_settings_file(settings_file,string):
    f = open(settings_file, "w")
    f.write(string)
    f.close()


def connect(LCD):
    #Connect to WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        LCD.fill(background_color)
        printstring("Waiting for connection...",10,15,1,main_color,LCD)
        print('Waiting for connection...')
        LCD.show()
        time.sleep(1)
    LCD.fill(background_color)
    printstring("Connection OK",15,15,1,main_color,LCD)
    LCD.show()

def api_call(LCD):
    gc.collect() # you have to collect garbage, because you run out memory
    LCD.fill(background_color)
    printstring("Requesting satelite data...",15,30,1,main_color,LCD)
    LCD.show()
    response = requests.get(f"{api_url}/{settings[0]}/{settings[1]}/{settings[2]}/10/0&apiKey={api_key}")
    response_code = response.status_code # could check it, I will not tho
    LCD.fill(background_color)
    return response.content

if __name__=='__main__':
    pwm = PWM(Pin(BL))
    pwm.freq(1000)
    pwm.duty_u16(32768)#max 65535

    main_color = color(100,100,100) # for lines, and text
    background_color = color(245,245,246) #pure white is just hurts the eye

    LCD = LCD_1inch3()
    #color BRG
    LCD.fill(background_color)
    LCD.show()
    
    connect(LCD)
   
    # buttons
    keyA = Pin(15,Pin.IN,Pin.PULL_UP)
    keyB = Pin(17,Pin.IN,Pin.PULL_UP)
    keyX = Pin(19 ,Pin.IN,Pin.PULL_UP)
    keyY= Pin(21 ,Pin.IN,Pin.PULL_UP)
    
    up = Pin(2,Pin.IN,Pin.PULL_UP)
    down = Pin(18,Pin.IN,Pin.PULL_UP)
    left = Pin(16,Pin.IN,Pin.PULL_UP)
    right = Pin(20,Pin.IN,Pin.PULL_UP)
    ctrl = Pin(3,Pin.IN,Pin.PULL_UP)
    
    # button timers, we need this so it doesn't repeat button press in every ms when the button is pressed
    keyA_last = time.ticks_ms()
    keyB_last = time.ticks_ms()
    right_last = time.ticks_ms()
    left_last = time.ticks_ms()
    up_last  = time.ticks_ms()
    down_last = time.ticks_ms()
    
    # create or read the settings from the settings file, it is not really needed as I never implemented settings view
    # settings[0] - lat | settings[1] - lng | settings[2] - elevation
    try:
        f = open(settings_file, "r")
        settings = f.read().split(";")
        f.close()
    except:
        write_settings_file(settings_file,base_settings)
        settings = base_settings.split(";")
    
    settings[0] = float(settings[0])
    settings[1] = float(settings[1])
    settings[2] = float(settings[2])
    
    # you can use this for debuging without API calls
    # satelite_above_data_json = '{"info":{"category":"Amateur radio","transactionscount":17,"satcount":3},"above":[{"satid":20480,"satname":"JAS 1B (FUJI 2)","intDesignator":"1990-013C","launchDate":"1990-02-07","satlat":49.5744,"satlng":-96.7081,"satalt":1227.9326},{"satid":26609,"satname":"AMSAT OSCAR 40","intDesignator":"2000-072B","launchDate":"2000-11-16","satlat":5.5105,"satlng":-21.4478,"satalt":49678.6389},{"satid":40719,"satname":"DEORBITSAIL","intDesignator":"2015-032E","launchDate":"2015-07-10","satlat":43.8106,"satlng":-90.3944,"satalt":657.5516}]}'
    
    satelite_above_data_json = api_call(LCD)
   
    satelite_above_data = ujson.loads(satelite_above_data_json)
    LCD.fill(background_color)
    
    # main loop
    while(1):
    
# ================== Controls ================== 
        if keyA.value() == 0:
            # mode switch button is button A satelites view (0) <-> settings view (1) 
            if time.ticks_diff(time.ticks_ms(), keyA_last) > 500:
                if view == 0:
                    view = 1
                    selected_setting = 0
                else:
                    view = 0
                    write_settings_file(settings_file,str(settings[0]) + ";" + str(settings[1]) + ";" + str(settings[2]))
                    above_in_view = 0
                    
                LCD.fill(background_color)    
                keyA_last = time.ticks_ms()
        
        
        
        # satelite view sepcific controls 
        if view == 0:
            if right.value() == 0:
                if time.ticks_diff(time.ticks_ms(), right_last) > step_time:
                    if above_in_view < satelite_above_data["info"]["satcount"] - 1:
                        above_in_view = above_in_view + 1
                    else:
                        above_in_view = 0
                    right_last = time.ticks_ms()
                    LCD.fill(background_color)
             
            if left.value() == 0:
                if time.ticks_diff(time.ticks_ms(), left_last) > step_time:
                    if above_in_view > 0:
                        above_in_view = above_in_view - 1
                    else:
                        above_in_view = satelite_above_data["info"]["satcount"] - 1
                    left_last = time.ticks_ms()
                    LCD.fill(background_color)
        
            if keyB.value() == 0:
                if time.ticks_diff(time.ticks_ms(), keyB_last) > api_refresh_time:
                    keyB_last = time.ticks_ms()
                    satelite_above_data_json = api_call(LCD)
                    satelite_above_data = ujson.loads(satelite_above_data_json)
                    above_in_view = 0
                else:
                    LCD.fill(background_color)
                    printstring("API time limit.",15,190,1,main_color,LCD)
                    printstring(f"Wait {math.floor((api_refresh_time/1000)-(time.ticks_diff(time.ticks_ms(), keyB_last)/1000))} seconds",15,210,1,LCD.red,LCD)
                    
        # settings view sepcific controls 
        #if view == 1:
            
            #if up.value() == 0:
            #    # if time.ticks_diff(time.ticks_ms(), up_last) > latlng_step_time:
            #        settings[selected_setting] = settings[selected_setting] + 0.01
            #        up_last = time.ticks_ms()
            #        LCD.fill(background_color)
            # 
            #if down.value() == 0:
            #    if time.ticks_diff(time.ticks_ms(), down_last) > latlng_step_time:
            #        
            #        down_last = time.ticks_ms()
            #        LCD.fill(background_color)
            
# ================== Satelites view ================== 
        if view == 0:
            draw_icon(0,208,15, LCD, main_color)
            draw_icon(1,208,75,LCD, main_color)
            
            # my original plan was showing images about satelites but nope. Feel free to do it.
            # LCD.rect(60,60,120,120,main_color)
            
            satelite_above_data["above"][0]
            
            printstring(f"Satelites: {above_in_view+1}/{satelite_above_data["info"]["satcount"]}",15,15,1,main_color,LCD)
            
            printstring(f"Name: {satelite_above_data["above"][above_in_view]["satname"]}",15,35,1,main_color,LCD)
            
            printstring(f"Launch Date: {satelite_above_data["above"][above_in_view]["launchDate"]}",15,55,1,main_color,LCD)
            
            printstring(f"lat:  {satelite_above_data["above"][above_in_view]["satlat"]}",15,75,1,main_color,LCD)
            
            printstring(f"lng: {satelite_above_data["above"][above_in_view]["satlng"]}",15,95,1,main_color,LCD)
            
            printstring(f"Altitude (km): {satelite_above_data["above"][above_in_view]["satalt"]}",15,115,1,main_color,LCD)
            
            
                
 # ================== Settings view ==================        
        if view == 1:
            
            printstring("Sorry I got bored doing this",10,15,1,main_color,LCD)
            
            printstring("Source code still have some",10,30,1,main_color,LCD)
            printstring("of the settings code",10,45,1,main_color,LCD)
            #printstring("S E T T I N G S",60,15,1,main_color,LCD)
            #
            #printstring("Set up your location",20,30,1,main_color,LCD)
            #
            #printstring("Latitude: ",20,60,1,main_color,LCD)
            #
            #printstring(str(settings[0]),100,60,1,main_color,LCD) 
            #
            #printstring("Latitude: ",20,80,1,main_color,LCD)
            #
            #printstring(str(settings[1]),100,80,1,main_color,LCD)
            #
            #printstring("Altitude (km): ",20,100,1,main_color,LCD)
            #
            #printstring(str(settings[2]),140,100,1,main_color,LCD)
            
            
      
       
        
            
        
        LCD.show()
    time.sleep(1)
    LCD.fill(0xFFFF)
