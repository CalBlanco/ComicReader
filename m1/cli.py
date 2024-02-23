from reader import Reader
import argparse

parser = argparse.ArgumentParser(description="CLI controls for CR")
parser.add_argument('-m', '--model', help='.pt for Object detection weights')
parser.add_argument('-t', '--ttsmodel', help='tts model string to use for tts')
parser.add_argument('-v', '--voice', help='voice wav to use for tts')
parser.add_argument('-me', '--meta', help='load meta file to read comic')

od_model = './best.pt'
tts_model = 'tts_models/multilingual/multi-dataset/your_tts'
voice_wav = './voices/morganfreeman.wav'
meta_location = None

if __name__ == "__main__":
    args = parser.parse_args()

    if args.model:
        od_model = args.model

    if args.ttsmodel:
        tts_model = args.ttsmodel
    
    if args.voice:
        voice_wav = args.voice

    if args.meta:
        meta_location = args.meta

    
    if meta_location:
        reader = Reader('',od_model,tts_model,voice_wav)

        reader.readFromMeta(meta_location)



