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
        self.read_bubbles = 0

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
        try:
            self.tts = TTS(self.tts_model).to(device)
        except:
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        self.model = YOLO(self.model_path) if not self.model else self.model
        self.reader = easyocr.Reader(['en'],gpu=True)
        self.speller = Speller()
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

    '''Clean out our text to aid in TTS
        removing certain chars that present problems and then feeding that replaced string into an autocorrecting library for further fixes
    '''
    def cleanTextForSpeech(self,text):
        text = text.lower()
        removes = [',','\'','#', '$', '%', '&', '*', '+', '_', '-','?','`', '.', ';', '(', ')', '[', ']', '{', '}']
        for re in removes:
            text = text.replace(re,'')
        
        replacements = {'0': 'o', '1': 'l', '6': 'g', '4':'y'} #these are just some common mistakes i saw it make could not be great
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
        #winsound.PlaySound('./audio_clips/current_bubble.wav', winsound.SND_FILENAME)
        #os.remove('./audio_clips/current_bubble.wav')
        return
    
    def audioProcess(self,audio_path):
        if not self.audio_proc:
            self.audio_proc = multiprocessing.Process(target=self.iterateAudio, args=(audio_path,))
            self.audio_proc.start()

    def iterateAudio(self,audio_path):
        files = os.listdir(audio_path)
        while len(files) <= 0:
            continue

        for page in files:
            clips = os.listdir(page)
            for clip in clips:
                winsound.PlaySound(clip,winsound.SND_FILENAME)
                os.remove(clip)
        print(files)

    '''Given a prediction grab the text if applicable and return it '''
    def readBubble(self, pair,img,save_name):
        x,y,w,h = [float(val) for val in pair["box"]]
        cl = int(pair["class"]) #shorthand for vars
        if (cl==0 or cl==2 or cl == 4 or cl == 5) and float(pair['conf']) > 0.7: # if the class is something we should read
            crop = img.crop((x-(w/2)-self.bubble_pad,y-(h/2)-self.bubble_pad,x+(w/2)+self.bubble_pad,y+(h/2)+self.bubble_pad)) #crop with padding
            crop_path = f"./crops/{save_name}.png" #crop file path
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
        index = pair['index']
        draw.rectangle((x-(w/2),y-(h/2),x+(w/2),y+(h/2)),width=3,outline=colors[cl])
        draw.text((x,y), f"Class: {cl}, Conf: {conf}, i: {index}", stroke_fill=colors[cl], fill=colors[cl])

    
    '''Crop out the bubbles containing speech hopefully'''
    def cropBubbles(self,save_name,src,page_num):
        def posIndex(box):
            x,y,_,_ = box
            return round(float(x)*2+float(y))
        print(save_name)
        spl = save_name.split('/')
        audio_page_dir = f'./audio_clips/{spl[0]}/{page_num}'
        if not os.path.exists(audio_page_dir):
            os.makedirs(audio_page_dir)

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
                    bubble_text = self.readBubble(pair,img,f"{save_name}-{i}")
                    self.voiceSpeakText(bubble_text,audio_page_dir,i)
                    out_text += f"{bubble_text}\n" # append for the text file
                        
                for i,pair in enumerate(pairs): #draw the boxes on the image
                    self.drawBoundingBox(pair,draw)
                
            img.save(f"./read/{save_name}.png","PNG")
        with open(f"./read/{save_name}.txt", "w") as log: #write a text file for the image from what we deciphered
            log.write(f"{'-'*20}\nText from {save_name}START\n\n{out_text}\n\nEND{'-'*20}")

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

    '''Selenium Driver to read the comic book based on a link'''
    def readComic(self,comic_page,mode):
        comic,issue = self.setUpNames(comic_page)
        save_name = f'{comic}/{issue}'
        if not os.path.exists(f'./read/{comic}'):
            os.makedirs(f'./read/{comic}')
        if not os.path.exists(f'./crops/{comic}'):
            os.makedirs(f'./crops/{comic}')
        if os.path.exists(f'./audio_clips/{comic}'):
            os.makedirs(f'./audio_clips/{comic}')
        
        self.audioProcess(f'./audio_clips/{comic}')
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
                self.cropBubbles(image_name,tempImagePath,i)
                time.sleep(0.12)
                
                os.remove(tempImagePath)
                pass
            next_button.click()
            time.sleep(0.05)
        
        driver.close()#close out the driver
