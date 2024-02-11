# Comic Reader

I want to be enable people to experience comic books auditorially

## Setup 
1. Clone the repo
2. cd into the appropriate version 
3. recommend creating a virtual environment in the folder
4. `pip install -r requirements.txt` to install required packages for the version
5. `python main.py` to run 

## System

### Comic Reading / Parsing

The literal viewing of the comic is being done via Selenium and relying on the website structure of `readcomicsonline.li`. The Selenium driver visits targetted links and is then able to screenshot and save the pages (for data collection / training later) or read the comic via our object detection -> ocr -> tts system

Currently all the things are done in selenium but I was thinking it might be nicer on the viewer to only process the images via selenium and then read through the comic in a nicer / cleaner way (zooming in on bubbles and stuff)

### Read vs Save
Read uses the pipeline of models to auditorially read a comic book, it also interacts with the site differently by downloading the source image of the comic page. This is done to improve the resolution of the image and thus the resolution of the text contained in the image

Save on the other hand uses the div containing the image and takes a screenshot at the selenium browser size (this is reduced in order to capture the entire image the responsive layout on the site only shows the whole image in smaller window sizes)

### OCR
All the OCR is being done via `easyocr` I have not done any finetuning on it yet (even though I really should) it is not super great at detecting all the characters. 

### TTS
The tts is being done via `coqui` or something like that i kinda forget the name. They have a bunch of different models/multilingual stuff that can be used which is nice. It is pretty slow, and part of me wants to change the reading system so the images and audio can be created for the comic and just read seamlessly instead of waiting on the TTS system (some longer chunks of text can take 20+seconds)