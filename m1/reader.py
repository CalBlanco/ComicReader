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
import torch
import winsound
from autocorrect import Speller
from TTS.api import TTS
import multiprocessing
import json
import sys

#I really want to redo all the file path shit it is just too damn messy
# Make a new folder for the comic and issue 
# create page folders
#  - annotated image
#  - annotation file 
#  - text file 
#  - audio files 
# 


device = "cuda" if torch.cuda.is_available() else "cpu"

'''Reader Class for use in the GUI'''
class Reader():
    def __init__(self, model_path:str):
        self.model_path = model_path
        self.active_proc = None #active reading subproccess
        self.active_driver = None #active selenium driver
        
        
        self.read_pages = 0
        self.total_pages = 0
        self.read_prog_bar = None

        
        if not os.path.exists('./read/'):
            os.makedirs('./read/')

        
        self.targets = []
        self.bubble_pad = 10

    def setPadding(self,pad:int):
        self.bubble_pad = pad

    '''Gui setting methods'''
    def setModel(self,path:str):
        self.model = YOLO(path)

    #call our subprocess
    def read_process(self,mode:str='read'):
        if not self.active_proc:
            print("starting read subprocess")
            self.active_proc = multiprocessing.Process(target=self.read_wrapper,args=(mode,))
            self.active_proc.start()

    def read_wrapper(self,mode:str):
        print("initializing models for subprocess")
        #init our models in the subprocess
        self.model = YOLO(self.model_path)#yolo OD model
        self.reader = easyocr.Reader(['en'],gpu=True) #easy ocr
        self.speller = Speller() #spell check
        for target in self.targets:
            self.readComic(target,mode)

    '''Kill our active process'''
    def proc_stop(self):
        if self.active_driver:
            self.active_driver.quit()
        if self.active_proc:
            self.active_proc.terminate()
        
    
    '''Directly Add a target link'''
    def addTargets(self,targets:list):
        if type(targets) == list: #set the list of targets
            self.targets = targets
        if type(targets) == str: #append a single target
            self.targets.append(targets)
    
    '''Add a list of targets by providing a file'''
    def addTargetByFile(self,file_path:str):
        if not os.path.exists(file_path):
            return
        
        with open(file_path) as li:
            self.targets = li.read().split("\n")

    '''Clean out unwanted tabs providing a driver and the original window you
    intend to keep 
    '''
    def cleanTabs(self,driver:webdriver,og_window:str):
        for window_handle in driver.window_handles:
            if window_handle != og_window:
                driver.switch_to.window(window_handle)
                driver.close()
        
        driver.switch_to.window(og_window)

    '''Center the image for reading / screenshotting
    '''
    def center_image(self,driver:webdriver,image_content:any):
        ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.SUBTRACT).key_up(Keys.CONTROL).perform()    
        ActionChains(driver)\
        .scroll_to_element(image_content)\
        .scroll_by_amount(-300,100)\
        .perform()
        time.sleep(0.15) #have to sleep here otherwise screenshot is fucked

    '''Capture the image content as a screenshot for data collection'''
    def takeScreenshot(self, image_content:any, save_name:str):
        image_content.screenshot(f'{save_name}/comic.png')

    #add error handling 
    '''Get the total pages, next button, and image content location'''
    def getPageItems(self,driver:webdriver):
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


    '''Grab the new image source for getting a fuller resolution image (helps with ocr)'''
    def getUpdatedImageSrc(self,driver:webdriver):
        image_link = driver.find_element(By.ID, 'imgCurrent')
        src = image_link.get_attribute("src")
        return src

    '''Save the file as a temp file and return the file path'''
    def saveFullImage(self,image_source:str):
        try:
            r = requests.get(image_source)
            assert r.status_code == 200, "Unable to get picture"
            with tempfile.NamedTemporaryFile(delete=False,suffix=".png") as tmp_file:
                tmp_file.write(r.content)
                return tmp_file.name
        except:
            return None

    '''Clean out our text to aid in TTS
        removing certain chars that present problems and then feeding that replaced string into an autocorrecting library for further fixes
    '''
    def cleanTextForSpeech(self,text:str):
        text = text.lower()
        removes = [',','\'','#', '$', '%', '&', '*', '+', '_', '-','?','`', '.', ';', '(', ')', '[', ']', '{', '}']
        for re in removes:
            text = text.replace(re,'')
        
        replacements = {'0': 'o', '1': 'l', '6': 'g', '4':'y', '@' : 'o'} #these are just some common mistakes i saw it make could not be great
        for re in replacements.keys():
            text = text.replace(re,replacements[re])

        text = self.speller(text)
        return text.lower()

    '''Given a prediction grab the text if applicable and return it '''
    def readBubble(self, pair,img):
        x,y,w,h = [float(val) for val in pair["box"]]
        cl = int(pair["class"]) #shorthand for vars
        if (cl==0 or cl==2 or cl == 4 or cl == 5) and float(pair['conf']) > 0.7: # if the class is something we should read
            crop = img.crop((x-(w/2)-self.bubble_pad,y-(h/2)-self.bubble_pad,x+(w/2)+self.bubble_pad,y+(h/2)+self.bubble_pad)) #crop with padding
            crop_path = f"cropped_bubble.png" #crop file path
            print(crop_path)
            crop.save(crop_path,"PNG") # save it for reading 
            text = self.reader.readtext(crop_path) #read
            os.remove(crop_path) #remove crop
            text = ' '.join([str(t[1]) for t in text]) #save to text string for this page
            return text

    '''Draw the bounding box around the prediction for checking accuracy'''
    def drawBoundingBox(self,pair,draw):
        colors = [(255,0,0),(0,255,0),(0,0,255),(255,0,255),(0,255,255),(255,255,0),(0,125,125),(125,0,125),(125,125,0),(255,255,255)]
        
        x,y,w,h = [float(val) for val in pair['box']]
        cl = int(pair['class'])
        conf = round(float(pair['conf']),3)
        draw.rectangle((x-(w/2),y-(h/2),x+(w/2),y+(h/2)),width=3,outline=colors[cl])
        draw.text((x,y-(h/2)), f"Class: {cl}, Conf: {conf}", stroke_fill=colors[cl], fill=colors[cl])

    
    '''Crop out the bubbles containing speech hopefully'''
    def cropBubbles(self,page_dir,src):
        def posIndex(box):
            x,y,_,_ = box
            return round(float(x)*2+float(y))
        out_text = ""
       
        with Image.open(src).convert("RGB") as img:
            img.save(f"{page_dir}/raw.png", "PNG")#save raw version for reading
            draw = ImageDraw.Draw(img)
            results = self.model([img])

            for result in results:
                boxes = result.boxes #get our boxes
                sizes = boxes.xywh #actual bounding box 
                classes = boxes.cls #classes
                conf = boxes.conf #confidence leves

                #store the info and sort it for the correct position of the boxes
                pairs = [{"box": sizes[i], "class": cl, 'conf': conf[i], 'index': posIndex(sizes[i]) } for i,cl in enumerate(classes)]
                pairs.sort(key=lambda x: (float(x['box'][1]), float(x['box'][0])) )

                #loop over boxes
                for i,pair in enumerate(pairs):
                    bubble_text = self.readBubble(pair,img)
                    out_text += f"{self.cleanTextForSpeech(bubble_text)}\n" if bubble_text is not None else "" # append for the text file

                for i,pair in enumerate(pairs): #draw the boxes on the image
                    self.drawBoundingBox(pair,draw)
                
            img.save(f"{page_dir}/anot.png","PNG") #save our annotated image (part of me wants to save the annotations we got as well)
        with open(f"{page_dir}/dialogue.txt", "w") as log: #write a text file for the image from what we deciphered
            log.write(f"{'-'*20}\n<START>\n\n{out_text}\n\n<END>{'-'*20}")

    '''Parse readcomiconline link for comic name and issue information'''
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

    '''Selenium Driver to read the comic book based on a link
        comic_page
    '''
    def readComic(self,comic_page:str,mode:str):
        
        comic,issue = self.setUpNames(comic_page)
        save_name = f'./read/{comic}/{issue}'
        print(save_name)

        #create the folder for the comic in the read folder
        if not os.path.exists(save_name):
            os.makedirs(save_name)

        #init our driver and go to the desired page collecting the elements we will need to read
        options = Options()
        options.add_argument("--log-level=3")
        driver = webdriver.Chrome(options=options)
        self.active_driver = driver
        driver.set_window_size(600, 800)
        driver.get(comic_page)

    
        og_window = driver.current_window_handle #save our original window 

        next_button, image_conent, total_pages= self.getPageItems(driver) #page elements we care about

        wait = WebDriverWait(driver, timeout=2)
        wait.until(lambda d: image_conent.is_displayed())
        #iterate over each page saving the contents as images
        #Here is where I think I am going to add processing for what I want to do 
        #Store the image, get any text from it, read off text, delete this image, go to next
        #self.read_prog_bar.set(0)
        for i in range(1,int(total_pages)-1):
            page_dir = f'{save_name}/{i}' #create the folder we will save our data into per page
            if not os.path.exists(page_dir):
                os.makedirs(page_dir)

            if len(driver.window_handles) > 1:#ensure this is the only tab open
                self.cleanTabs(driver,og_window)

            self.center_image(driver,image_conent)

            if mode == 'save': #if in save mode just take a screenshot for the page
                self.takeScreenshot(image_conent,page_dir)

            if mode == 'read': #if in read mode get the full res image, and read it
                src = self.getUpdatedImageSrc(driver)
                tempImagePath = self.saveFullImage(src)
                if not tempImagePath: #if the image can not be recieved just try the next one 
                    continue
               
                self.cropBubbles(page_dir,tempImagePath) #Crop / Process the bubbles
                time.sleep(0.12)
                os.remove(tempImagePath) #at this point this is technically double work (saving the raw image inread mode so we could just doo that but idk im lazy rn)
                
            next_button.click() #go to next page
            #self.read_prog_bar.step()
            time.sleep(0.05)
            
        self.saveComicData(save_name,total_pages-2) #-2 because we start 1 page after  the first (readcomic online puts an ad on the first page always)

        driver.close()#close out the driver

    def saveComicData(self,save_name,page_count):
        with open(f'{save_name}/meta.json', 'w') as meta:
            meta_data = {
                'path': save_name,
                'pages': page_count,
            }

            meta.write(json.dumps(meta_data,indent=3))
  