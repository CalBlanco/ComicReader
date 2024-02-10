from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
import time
import requests
import tempfile
import os
from ultralytics import YOLO
import easyocr
from PIL import Image, ImageDraw
import pyttsx3
from TTS.api import TTS
import torch
import winsound


device = "cuda" if torch.cuda.is_available() else "cpu"

class Reader():
    def __init__(self, out_path, model_path, voice_path, gpu_enabled=False):
        self.out_path = out_path
        self.voice_path = voice_path
        self.model = None
        self.model_path = model_path
        #make needed directories
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        if not os.path.exists('./crops/'):
            os.makedirs('./crops/')
        if not os.path.exists('./read/'):
            os.makedirs('./read/')
        if not os.path.exists('./audio_clips/'):
            os.makedirs('./audio_clips/')

        
        self.targets = []

    def setModel(self,path):
        self.model = YOLO(path)

    def setVoice(self, voice_path):
        self.voice_path = voice_path

    def read(self,mode='save'):
        #init models
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        self.model = YOLO(self.model_path) if not self.model else self.model
        self.reader = easyocr.Reader(['en'],gpu=True)

        for target in self.targets:
            self.readComic(target,mode)

    '''Directly Add a target link'''
    def addTargets(self,targets):
        if type(targets) == list: #set the list of targets
            self.targets = targets
        if type(targets) == str: #append a single target
            self.targets.append(targets)
    
    '''Add a list of targets by providing a file'''
    def addTargetByFile(self,file_path):
        if not os.path.exists(file_path):
            return
        
        with open(file_path) as li:
            self.targets = li.read().split("\n")

    '''Clean out unwanted tabs providing a driver and the original window you
    intend to keep 
    '''
    def cleanTabs(self,driver,og_window):
        for window_handle in driver.window_handles:
            if window_handle != og_window:
                driver.switch_to.window(window_handle)
                driver.close()
        
        driver.switch_to.window(og_window)

    '''Take a screenshot for data collection
        (not to be confusedf with getting full source)
    '''
    def center_image(self,driver,image_content):
        ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.SUBTRACT).key_up(Keys.CONTROL).perform()    
        ActionChains(driver)\
        .scroll_to_element(image_content)\
        .scroll_by_amount(-300,100)\
        .perform()
        time.sleep(0.15) #have to sleep here otherwise screenshot is fucked

    def takeScreenshot(self, image_content, save_name):
        image_content.screenshot(f'{self.out_path}/{save_name}')


    '''Get the total pages, next button, and image content location'''
    def getPageItems(self,driver):
        next_button = driver.find_element(By.ID, "btnNext")
        image_conent = driver.find_element(By.ID, "divImage")
        dropdown_element = driver.find_element(By.ID, 'selectPage')
        image_link = image_conent.find_element(By.ID, 'imgCurrent')
        src = image_link.get_attribute("src")
        # Create a Select object using the dropdown element
        select = Select(dropdown_element)

        # Get all the options
        options = select.options

        # Determine the number of options
        total_pages = len(options)
        print(f"Found {total_pages} total pages")
        return [next_button,image_conent,total_pages]


    '''Grad the new image source for getting a fuller resolution image (helps with ocr)'''
    def getUpdatedImageSrc(self,driver):
        image_link = driver.find_element(By.ID, 'imgCurrent')
        src = image_link.get_attribute("src")
        return src

    '''Save the file as a temp file and return the file path'''
    def saveFullImage(self,image_source):
        r = requests.get(image_source)
        assert r.status_code == 200, "Unable to get picture"
        with tempfile.NamedTemporaryFile(delete=False,suffix=".png") as tmp_file:
            tmp_file.write(r.content)
            return tmp_file.name


    #updated TTS
    def voiceSpeakText(self,text):
        self.tts.tts_to_file(text=f"{text}", speaker_wav="./syeun.wav", language="en", file_path="./audio_clips/current_bubble.wav")
        winsound.PlaySound('./audio_clips/current_bubble.wav', winsound.SND_FILENAME)
        time.sleep(1.5)
        os.remove('./audio_clips/current_bubble.wav')
        return

    
    def cropBubbles(self,save_name,src):
        print(save_name)
        out_text = ""
        colors = [(255,0,0),(0,255,0),(0,0,255),(0,0,255),(0,0,255),(0,0,255),(0,0,255),(0,0,255),(0,0,255),(0,0,255)]
        PAD = 10
        with Image.open(src).convert("RGB") as img:
            draw = ImageDraw.Draw(img)
            results = self.model([img])

            for result in results:
                boxes = result.boxes
                sizes = boxes.xywh
                classes = boxes.cls

                pairs = [{"box": sizes[i], "class": cl } for i,cl in enumerate(classes)]
                pairs.sort(key=lambda x: ( float(x["box"][1]), float(x["box"][0]) ) )
                for i,pair in enumerate(pairs):
                    x,y,w,h = [float(val) for val in pair["box"]]
                    cl = int(pair["class"])
                    if cl==0 or cl==2 or cl == 4 or cl == 5: # if the class is something we should read
                        crop = img.crop((x-(w/2)-PAD,y-(h/2)-PAD,x+(w/2)+PAD,y+(h/2)+PAD)) #crop with padding
                        crop_path = f"./crops/crop-{save_name}-{i}.png" #crop file path
                        crop.save(crop_path,"PNG") # save it for reading 
                        text = self.reader.readtext(crop_path) #read
                        os.remove(crop_path) #remove crop
                        text = ' '.join([str(t[1]) for t in text]) #save to text string for this page
                        if text == '': 
                            continue
                        self.voiceSpeakText(text)
                        out_text += f"{'='*10}\nFROM BOX: [{x},{y},{x+w},{y+h}]\n\n{text}\n" # append for the text file
                        
                for i,cl in enumerate(classes): #draw the boxes on the image
                    x,y,w,h = [float(val) for val in sizes[i]]
                    cl = int(cl)
                    draw.rectangle((x-(w/2),y-(h/2),x+(w/2),y+(h/2)),width=3,outline=colors[cl])
                    draw.text((x,y), f"Class: {cl}", stroke_fill=colors[cl])
                
            img.save(f"./read/{save_name}-{i}.png","PNG")
        with open(f"./read/{save_name}.txt", "w") as log: #write a text file for the image from what we deciphered
            log.write(f"{'-'*20}\nText from {save_name}START\n\n{out_text}\n\nEND{'-'*20}")

    def setUpNames(self, comic_page):
            link = comic_page.find("https://") if comic_page.find("https://") > -1 else 0
            assert link != '','Invalid link'
            query = comic_page.find("?") if comic_page.find("?") > -1 else len(comic_page)
            comic_page = comic_page[link+len('https://'):query] #remove the prefix and query data
            print(comic_page)
            comic_page = comic_page.split("/")
            _,_,comic,issue = comic_page
            print(f"found comic name {comic}/{issue}")
            return [comic,issue]

    #read the comic
    def readComic(self,comic_page,mode):
        save_name = self.setUpNames(comic_page)
        save_name = f'{save_name[0]}-{save_name[1]}'
        #init our driver and go to the desired page collecting the elements we will need to read
        options = Options()
        options.add_argument("--log-level=3")
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(600, 800)
        driver.get(comic_page)

    
        og_window = driver.current_window_handle

        next_button, image_conent, total_pages= self.getPageItems(driver)

        wait = WebDriverWait(driver, timeout=2)
        wait.until(lambda d: image_conent.is_displayed())
        #iterate over each page saving the contents as images
        #Here is where I think I am going to add processing for what I want to do 
        #Store the image, get any text from it, read off text, delete this image, go to next
        for i in range(1,int(total_pages)-1):
            image_name = f'{save_name}-{i}'
            if len(driver.window_handles) > 1:
                self.cleanTabs(driver,og_window)

            self.center_image(driver,image_conent)
            if mode == 'save':
                self.takeScreenshot(image_conent,f'{image_name}.png')
            if mode == 'read':
                src = self.getUpdatedImageSrc(driver)
                tempImagePath = self.saveFullImage(src)
                # need to reimplment the reading code here
                self.cropBubbles(image_name,tempImagePath)
                time.sleep(0.12)
                os.remove(tempImagePath)
                pass
            next_button.click()
            time.sleep(0.05)
        
        driver.close()#close out the driver
