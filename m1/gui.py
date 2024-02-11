import tkinter as tk
from tkinter import filedialog
from tkinter import ttk, font
# GUI for comic reader development / program
# at the end i will want seperate gui for the model training and the reading, but for now I would like to have both in a package thats easy to interact with
from reader import Reader



# Screen 0: Option to run the comic reader on a list of links or a singular provided link (option to save for collection or read)
#  
class ReaderScreen(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        self.comic_reader = Reader('./out/','./best.pt') #init reader 

        #Tab layout for the reader and its settings
        tabs = ttk.Notebook(self)
        label = ttk.Label(self,text="Reading Screen", font=("Helvetica", 20))#title
        label.pack(padx=10, pady=10)

        read_frame = ttk.Frame(tabs) #frame for the reading operations
        input_frame = ttk.Frame(read_frame)
    
        link_label = ttk.Label(input_frame, text="By Link Input", font=('Helvetica', 12))#label for link input
        link_label.grid(row=0, column=0,padx=5,pady=5)
        link_str = tk.StringVar() #variable to contain link input
        link_entry = ttk.Entry(input_frame,textvariable=link_str) #link input
        link_entry.grid(row=0, column=1,padx=5,pady=5)
        link_entry.bind('<Return>', lambda x: self.addSingleTarget(link_str),link_str.set('')) #bind return event to add link and clear the entry field
        
        file_label = ttk.Label(input_frame, text="Or By File", font=('Helvetica', 12)) #file input label
        file_label.grid(row=3, column=0,padx=5,pady=5)
        self.file_path_str = tk.StringVar(value='')
        file_button = ttk.Button(input_frame,text="Select file", command=lambda: self.select_dir())
        file_button.grid(row=3, column=1,padx=5,pady=5)
        file_label_disc = ttk.Label(input_frame, text="File selection will overwrite list items", font=('Helvetica', 10))
        file_label_disc.grid(row=4,column=0,padx=5,pady=5)

        input_frame.pack()

        #display the targets we want to read
        target_frame = ttk.Frame(read_frame)
        self.list_box = tk.Listbox(target_frame,width=100,height=len(self.comic_reader.targets)*50)
        self.list_box.insert(tk.END, "Comic - Issue")
        self.list_box.pack(padx=10,pady=10)
        target_frame.pack()
        
        #holds modes (read or save)
        mode_frame = ttk.Frame(read_frame)
        read_mode_button = ttk.Button(mode_frame, text="Read Mode", command= lambda: self.comic_reader.threadRun('read'))
        save_mode_button = ttk.Button(mode_frame, text="Save Mode(copy pictures)", command= lambda: self.comic_reader.threadRun('save'))

        read_mode_button.grid(row=0,column=0, padx=10)
        save_mode_button.grid(row=0,column=2, padx=10)
        stop_button = ttk.Button(mode_frame,text="Stop", command=lambda: self.comic_reader.threadStop())
        stop_button.grid(row=1,column=1, padx=10, pady=10)
        mode_frame.pack()

        

        read_frame.pack()

        #settings tab
        settings_frame = ttk.Frame(tabs)
        #yolo model weights
        model_label = ttk.Label(settings_frame, text="Pick Object Detector", font=("Helvetica", "12"))
        model_entry = ttk.Button(settings_frame, text="Select File", command=lambda: self.setModel())
        current_model = ttk.Label(settings_frame, text=f"{self.comic_reader.model_path}")
        current_model.grid(row=0,column=2,padx=10, pady=10)
        model_label.grid(row=0,column=0,padx=10,pady=10)
        model_entry.grid(row=0,column=1,padx=10,pady=10)
        #voice path (soon to be paths)
        voice_label = ttk.Label(settings_frame, text="Change the speakers voice", font=("Helvetica", "12"))
        voice_entry = ttk.Button(settings_frame, text="Select File", command=lambda: self.setVoice())
        current_voice = ttk.Label(settings_frame, text=f"{self.comic_reader.voice_path}")
        voice_label.grid(row=1,column=0,padx=10,pady=10)
        voice_entry.grid(row=1,column=1,padx=10,pady=10)
        current_voice.grid(row=1,column=2,padx=10, pady=10)
        #bubble pad size
        pad_label = ttk.Label(settings_frame, text="Text Bubble Padding", font=('Helvetica', '12'))
        pad_int = tk.IntVar(value=self.comic_reader.bubble_pad)
        pad_entry = ttk.Entry(settings_frame,textvariable=pad_int)
        pad_entry.bind('<Return>', lambda x: self.comic_reader.setPadding(pad_int.get()))
        pad_label.grid(row=2,column=0,padx=10,pady=10)
        pad_entry.grid(row=2,column=1,padx=10,pady=10)
        #tts model by string entry
        tts_label = ttk.Label(settings_frame, text="TTS Model", font=('Helvetica', '12'))
        tts_string = tk.StringVar()
        tts_entry = ttk.Entry(settings_frame, textvariable=tts_string)
        tts_entry.bind('<Return>', lambda x: self.comic_reader.setTTSModel(tts_string.get()))
        tts_label.grid(row=3,column=0,padx=10,pady=10)
        tts_entry.grid(row=3,column=1,padx=10,pady=10)

        settings_frame.pack()

        tabs.add(read_frame, text="Reader")
        tabs.add(settings_frame, text="Settings")
        tabs.pack()


        

    def setVoice(self):
        path = filedialog.askopenfilename(filetypes=(('Wave Files','*.wav'),("All files", "*.*")))
        if path:
            self.comic_reader.setVoice(path)
    
    def setModel(self):
        path = filedialog.askopenfilename(filetypes=(('Pytorch Weights', '*.pt'),("All files", "*.*")))
        if path:
            self.comic_reader.setModel(path)


    def addSingleTarget(self,link_str):
        self.comic_reader.addTargets(link_str.get())
        self.populate_list()

    def populate_list(self):
        self.list_box.delete(0,tk.END)
        self.list_box.insert(tk.END, "Comic - Issue")
        for t in self.comic_reader.targets:
            comic,issue = self.comic_reader.setUpNames(t)
            self.list_box.insert(tk.END, f"{comic} - {issue}")

    def select_dir(self):
        dir = filedialog.askopenfilename(filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if dir:
            self.file_path_str.set(dir)
            self.comic_reader.addTargetByFile(dir)
            
        self.populate_list()
        


# Screen 1: Data building feature, prompt two folder inputs (images and labels) then build our data yaml accordingly as well as move files into appropriate folders
class DataBuilderScreen(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        label = tk.Label(self,text="Data Builder Screen", font=("Helvetica", 20))
        label.pack(padx=10,pady=10)

        

        

# Screen 2: Yolo Trainer 
class YoloScreen(tk.Frame):
    def __init__(self,master):
        super().__init__(master)

        label = tk.Label(self,text="Trainer Screen", font=("Helvetica", 20))
        label.pack(padx=10,pady=10)


#Main App Screen
class MainApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.geometry("1000x900")
        self.title("Comic Reader GUI")


        self.notebook = ttk.Notebook(self,width=900,height=800)
        tab1 = ReaderScreen(self.notebook)
        tab2 = DataBuilderScreen(self.notebook)
        tab3 = YoloScreen(self.notebook)
        self.notebook.add(tab1, text='Reader')
        self.notebook.add(tab2, text='Data Builder')
        self.notebook.add(tab3, text='Yolo Model Trainer')
        self.notebook.pack()
        self.bind('<Escape>', lambda x: self.quit())