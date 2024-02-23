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
    def __init__(self, out_path, model_path, tts_model='tts_models/multilingual/multi-dataset/your_tts',voice_path='voices/omniman/omniman.wav'):
        self.out_path = out_path
        self.voice_path = voice_path
        self.model = None
        self.tts_model = tts_model
        self.model_path = model_path
        self.active_proc = None
        self.active_driver = None
        self.audio_proc = None
        try:
            self.tts = TTS(self.tts_model).to(device)
        except:
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        self.model = YOLO(self.model_path) if not self.model else self.model
        self.reader = easyocr.Reader(['en'],gpu=True)
        self.speller = Speller()
        
        self.read_pages = 0
        self.total_pages = 0
        self.read_prog_bar = None

        #make needed directories
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        if not os.path.exists('./read/'):
            os.makedirs('./read/')

        
        self.targets = []
        self.bubble_pad = 10

    def setPadding(self,pad):
        self.bubble_pad = pad

    '''Gui setting methods'''
    def setModel(self,path):
        self.model = YOLO(path)

    def setTTSModel(self, modelString):
        print(f"Setting TTS model to {modelString}")
        self.tts_model = modelString

    def setVoice(self, voice_path):
        self.voice_path = voice_path
    '''Start a reading process if we don't have one'''
    def threadRun(self,runMode='read'):
        if not self.active_proc:
            self.active_proc = multiprocessing.Process(target=self.readWrapper,args=(runMode,))
            self.active_proc.start()
        return

    '''Kill our active process'''
    def threadStop(self):
        if self.active_driver:
            self.active_driver.quit()
        if self.active_proc:
            self.active_proc.terminate()
        if self.audio_proc:
            self.audio_proc.terminate()
        
    '''Functin to call reader through gui'''
    def readWrapper(self,mode='read'):
        #init models
        print('Read Wrapper beggining read operation')
        
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

    '''Center the image for reading / screenshotting
    '''
    def center_image(self,driver,image_content):
        ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.SUBTRACT).key_up(Keys.CONTROL).perform()    
        ActionChains(driver)\
        .scroll_to_element(image_content)\
        .scroll_by_amount(-300,100)\
        .perform()
        time.sleep(0.15) #have to sleep here otherwise screenshot is fucked

    '''Capture the image content as a screenshot for data collection'''
    def takeScreenshot(self, image_content, save_name):
        image_content.screenshot(f'{save_name}/comic.png')


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

    '''Clean out our text to aid in TTS
        removing certain chars that present problems and then feeding that replaced string into an autocorrecting library for further fixes
    '''
    def cleanTextForSpeech(self,text):
        text = text.lower()
        removes = [',','\'','#', '$', '%', '&', '*', '+', '_', '-','?','`', '.', ';', '(', ')', '[', ']', '{', '}']
        for re in removes:
            text = text.replace(re,'')
        
        replacements = {'0': 'o', '1': 'l', '6': 'g', '4':'y', '@' : 'o'} #these are just some common mistakes i saw it make could not be great
        for re in replacements.keys():
            text = text.replace(re,replacements[re])

        text = self.speller(text)
        return text

    '''TTS using Coqui(soon to be bark)'''
    def voiceSpeakText(self,text,page_dir,bubble_num):
        if text is None or text=='': 
            return
        text = self.cleanTextForSpeech(text)
        clip_path = f"{page_dir}/{bubble_num}"
        self.tts.tts_to_file(text=text, file_path=f'{clip_path}.wav', language='en', speaker_wav=self.voice_path,split_sentences=True)
        # commented out the reading portion, want to try iterating through first
        #winsound.PlaySound(clip_path, winsound.SND_FILENAME)
        #os.remove('./audio_clips/current_bubble.wav')
        return
    
    #more generic string reader, perform some basic cleaning then ask to read outloud
    # if no savename is passed file is removed after being read outloud
    # read_now by default will read the processed text
    def readString(self,text,voice=None, read_now=True,save_name=None):
        if text is None or text=='': 
            return
        text = self.cleanTextForSpeech(text)
        save = 'temp_voice.wav' if save_name is None else save_name
        self.tts.tts_to_file(text=text, file_path=save, language='en', speaker_wav=voice if voice is not None else self.voice_path, split_sentences=True )
        if read_now:
            winsound.PlaySound(save, winsound.SND_FILENAME)
        if save_name is None:
            os.remove(save)


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
        draw.text((x,y-(h/2)), f"Class: {cl}, Conf: {conf}", stroke_fill=colors[cl], stroke_width=2, fill=colors[cl])

    
    '''Crop out the bubbles containing speech hopefully'''
    def cropBubbles(self,page_dir,src):
        def posIndex(box):
            x,y,_,_ = box
            return round(float(x)*2+float(y))
        out_text = ""
       
        with Image.open(src).convert("RGB") as img:
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
                    #self.voiceSpeakText(bubble_text,page_dir,i)
                    out_text += f"{bubble_text}\n" if bubble_text is not None else "" # append for the text file

                for i,pair in enumerate(pairs): #draw the boxes on the image
                    self.drawBoundingBox(pair,draw)
                
            img.save(f"{page_dir}/anot.png","PNG")
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


        #self.audioProcess(f'./audio_clips/{comic}')
        #init our driver and go to the desired page collecting the elements we will need to read
        options = Options()
        options.add_argument("--log-level=3")
        driver = webdriver.Chrome(options=options)
        self.active_driver = driver
        driver.set_window_size(600, 800)
        driver.get(comic_page)

    
        og_window = driver.current_window_handle

        next_button, image_conent, total_pages= self.getPageItems(driver)

        
        wait = WebDriverWait(driver, timeout=2)
        wait.until(lambda d: image_conent.is_displayed())
        #iterate over each page saving the contents as images
        #Here is where I think I am going to add processing for what I want to do 
        #Store the image, get any text from it, read off text, delete this image, go to next
        #self.read_prog_bar.set(0)
        for i in range(1,int(total_pages)-1):
            
            page_dir = f'{save_name}/{i}'
            if not os.path.exists(page_dir):
                os.makedirs(page_dir)
            if len(driver.window_handles) > 1:
                self.cleanTabs(driver,og_window)

            self.center_image(driver,image_conent)
            if mode == 'save':
                self.takeScreenshot(image_conent,page_dir)
            if mode == 'read':
                src = self.getUpdatedImageSrc(driver)
                tempImagePath = self.saveFullImage(src)
                # need to reimplment the reading code here
                self.cropBubbles(page_dir,tempImagePath)
                time.sleep(0.12)
                os.remove(tempImagePath)
                
            next_button.click()
            #self.read_prog_bar.step()
            time.sleep(0.05)
            
        self.saveComicData(save_name,total_pages-1)
        self.readFromMeta(save_name)

        driver.close()#close out the driver

    def saveComicData(self,save_name,page_count):
        with open(f'{save_name}/meta.json', 'w') as meta:
            meta_data = {
                'path': save_name,
                'pages': page_count,
            }

            meta.write(json.dumps(meta_data,indent=3))
  

    #Read a comic based on the meta data file that was generated
    def readFromMeta(self,meta_location):
        print(meta_location)
        try: #try to find and open the meta.json from the specified path
            with open(f'{meta_location}/meta.json', 'r') as meta:
                meta_data = json.loads(meta.read())
                read_path = meta_data['path']
                total_pages = meta_data['pages']

            comic_path = os.path.join(os.getcwd(),read_path) #get the path of the comic files 
            if not os.path.exists(comic_path):
                print('Comic not found at path')
                return
            
            
            dirs = os.listdir(comic_path)
            print(dirs)
            dirs = [d for d in dirs if d.isdigit()]
            dirs = sorted(dirs,key=int)
            for i in dirs:
                path = os.path.join(comic_path,i)
                if os.path.isdir(path):
                    with open(f'{path}/dialogue.txt') as dialogue:
                        text_lines = self.parseDialogue(dialogue.read())
                        for line in text_lines:
                            self.readString(line)


        except FileNotFoundError:
            print('Unable to locate meta file')
            return
        except ValueError:
            print('Unablet to parse json')
            return 
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(f'Ooops - {exc_type.__name__} : {exc_value}')
            return
    
    #return an array of lines for each dialogue box
    def parseDialogue(self,text:str):
        start = text.find('<START>')
        end = text.find('<END>')

        text = text[start+len('<START>'):end]
        return text.split('\n') 