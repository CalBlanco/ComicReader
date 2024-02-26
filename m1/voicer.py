from TTS.api import TTS
import winsound
import torch
import os
import json
import multiprocessing
import sys

device = "cuda" if torch.cuda.is_available() else "cpu"
# a class to read text with a particular voice and tts model
class Voicer():
    def __init__(self, voice_path:str,tts_model:str="tts_models/multilingual/multi-dataset/xtts_v2"):
        self.voice_path = voice_path
        try: #try to use specified but default to the quality one (long processing time but much better outputs)
            self.tts = TTS(tts_model).to(device)
        except:
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    #more generic string reader, perform some basic cleaning then ask to read outloud
    # if no savename is passed file is removed after being read outloud
    # read_now by default will read the processed text
    def readString(self,text:str,save_name:str=None,read_now:bool=True):
        if text is None or text=='': 
            return
        #text = self.cleanTextForSpeech(text) #clean the text

        save = 'temp_voice.wav' if save_name is None else save_name

        self.tts.tts_to_file(text=text, file_path=save, language='en', speaker_wav=self.voice_path, split_sentences=True )

        if read_now:
            winsound.PlaySound(save, winsound.SND_FILENAME)
        if save_name is None:
            os.remove(save)

    #Read a comic based on the meta data file that was generated
    def readFromMeta(self,meta_location:str,read_now:bool):
        print(meta_location)
        try: #try to find and open the meta.json from the specified path
            with open(f'{meta_location}/meta.json' if meta_location.find('meta.json') == -1 else meta_location, 'r') as meta:
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
                        if not os.path.exists(f'{path}/audio'): #create a audio folder for the page
                            os.makedirs(f'{path}/audio')
                        for i,line in enumerate(text_lines): #enumerating over the bubbles read them and save the files seperately
                            self.readString(line,f'{path}/audio/{i}.wav',read_now)


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
        