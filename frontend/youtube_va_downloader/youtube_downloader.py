from tkinter import *
from tkinter import filedialog
from tkinter import messagebox
import tkinter.font as font
import os, threading, traceback
from PIL import ImageTk, Image

from .search_video import search_youtube_video
from .format_display import FormatUtils
from .download_video import YtDownloadFormat, audio_filetypes, DLUtils
from .set_up import SetupFile
from .download_requests import DownloadRequests


#list to store the remembered photos
photo_lst = {}

#list to store the remembered search and download pages opened
displayed_search_pages = {}
download_pages_lsts = {}
video_att_frame_lsts = {}

#return values for the different threads
processes = {}

setting_file = None
setting_data = None

root = None
sc_width =  None
sc_height = None



# a subclass of Canvas that is able to resize to change in dimensions of parent
class ResizingCanvas(Canvas):
    def __init__(self,parent,**kwargs):
        Canvas.__init__(self,parent,**kwargs)
        self.bind("<Configure>", self.on_resize)
        self.height = self.winfo_reqheight()
        self.width = self.winfo_reqwidth()
        self.is_resizing = False


    #rescales the canvas and every content within the canvas
    def on_resize(self,event):
        # flag whether the canvas is resizing
        self.is_resizing = True

        # determine the ratio of old width/height to new width/height
        wscale = float(event.width)/self.width
        hscale = float(event.height)/self.height
        self.width = event.width
        self.height = event.height

        sc_width = self.width
        sc_height = self.height

        # resize the canvas
        self.config(width=self.width, height=self.height)
        # rescale all the objects tagged with the "all" tag
        self.scale("all",0,0,wscale,hscale)

        self.is_resizing = False




# A frame that is scrollable
class ScrollFrame():
    def __init__(self, master, outer_frame, canvas, inner_frame, scrollbar):
        self.master = master
        self.outer_frame = outer_frame
        self.canvas = canvas
        self.scrollbar = scrollbar

        self.inner_frame = inner_frame
        self.inner_frame.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.bind_all("<MouseWheel>", lambda event, master=self.canvas: self.mouse_wheel(event, master))
        self.canvas.bind_all("<Up>", lambda event, master=self.canvas, key_pressed="up": self.mouse_wheel(event, master, key_pressed))
        self.canvas.bind_all("<Down>", lambda event, master=self.canvas, key_pressed="down": self.mouse_wheel(event, master, key_pressed))
        self.canvas.bind_all("<Button-4>", lambda event, master=self.canvas: self.mouse_wheel(event, master))
        self.canvas.bind_all("<Button-5>", lambda event, master=self.canvas: self.mouse_wheel(event, master))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)


    #moves the view of the canvas based of the ScrollFrame based the user's scrolling or pressing the up/down arrow keys
    def mouse_wheel(self, event, master, key_pressed = ""):
        if (event.num == 5 or event.delta == -120 or key_pressed == "down"):
            master.yview('scroll', 1, 'units')
        if (event.num == 4 or event.delta == 120 or key_pressed == "up"):
            master.yview('scroll', -1, 'units')


    #packs the ScrollFrame and enables the scrolling/arrow events on the canvas of the ScrollFrame
    def pack_frame(self, page_num=None):
        if (page_num is not None):
            #reconfigure the scrollbar to the desired search page
            self.canvas.bind_all("<MouseWheel>", lambda event, master=self.canvas: self.mouse_wheel(event, master))
            self.canvas.bind_all("<Up>", lambda event, master=self.canvas, key_pressed="up": self.mouse_wheel(event, master, key_pressed))
            self.canvas.bind_all("<Down>", lambda event, master=self.canvas, key_pressed="down": self.mouse_wheel(event, master, key_pressed))
            self.canvas.bind_all("<Button-4>", lambda event, master=self.canvas: self.mouse_wheel(event, master))
            self.canvas.bind_all("<Button-5>", lambda event, master=self.canvas: self.mouse_wheel(event, master))
            self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.outer_frame.pack(anchor="nw", fill="both", expand="yes")
        self.canvas.pack(side="right", fill="both", expand="yes")
        self.scrollbar.place(relx=1.0, rely=0.5,relheight=1.0,anchor="e")

    # hides the ScrollFrame and disables the scrolling/arrow events on the canvas of the ScrollFrame
    def pack_forget(self):
        self.scrollbar.place_forget()
        self.canvas.pack_forget()
        self.outer_frame.pack_forget()
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Up>")
        self.canvas.unbind_all("<Down>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    #deletes the ScrollFrame
    def destroy_frame(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Up>")
        self.canvas.unbind_all("<Down>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

        self.inner_frame.destroy()
        self.scrollbar.destroy()
        self.canvas.destroy()
        self.outer_frame.destroy()




'''
Provides a question path using radiobuttons

A NestedRadioButton is either:
    - NestedRadioButton
    - None
'''
class NestedRadioButton():
    def __init__(self, master,question,children, video=None, page_found=None):
        self.master = master
        self.button_frame = Frame(self.master, bg="white")

        self.question_font = font.Font(size=10, weight="bold")
        self.question_label = Label(self.button_frame, justify="left",font=self.question_font,bg="white")
        self.question_label.config(text=question)
        self.children = children
        self.var = StringVar()
        self.var.set(list(self.children.keys())[0])
        self.query = []
        self.query_pos = None
        self.options = []
        self.folder_frame = None
        self.confirm_button = None
        self.video = video
        self.page_found = page_found


    #Creates question and radio buttons for the current NestedRadioButton
    def make_button(self):
        self.button_frame.pack()
        self.question_label.pack(ipady="20")

        #creates the radio buttons if they are not made yet
        if (not self.options):
            for c in self.children:
                radio_button = Radiobutton(self.button_frame, text=c, variable=self.var, value=c, command=self.button_selected, bg="white", cursor="hand2")
                self.options.append(radio_button)
                radio_button.pack(ipady="5")

        #pack the radio buttons if they are already made
        else:
            for o in self.options:
                o.pack(ipady="10")


    #Creates the child NextedRadioButton when a certain RadioButton is pressed by the user
    def button_selected(self):
        answer = str(self.var.get())

        #remembers the RadioButton options pressed by the user
        if ((self.query_pos is None) or (self.query_pos >= len(self.query))):
            self.query.append(answer)
            self.query_pos = len(self.query) - 1

        else:
            self.query[self.query_pos] = answer
            self.query = self.query[:self.query_pos + 1]

        selected_child = self.children[answer]

        #Hides all of the previous children of the current RadioButton that appeared on screen
        self.unpack_children()

        #Hides the 'download' button and the 'choose folder' if the buttons have already appeared on screen
        if (self.confirm_button is not None):
            self.confirm_button.pack_forget()

        if (self.folder_frame is not None):
            self.folder_frame.pack_forget()

        #copy the current remembered options to the selected child
        if (selected_child is not None):
            selected_child.query = self.query

            selected_child.make_button()

        #create the 'choose folder' button if the child is None
        else:
            if (self.video is None):
                print("Missing Video in NestedRadioButton")
            else:
                choose_folder_font = font.Font(size=10)
                self.folder_frame = Frame(self.button_frame, bg="white")
                self.question_folder = Label(self.folder_frame, justify="left", text="Choose a Folder to Place the Download",font=self.question_font,bg="white")
                self.choose_folder = Button(self.folder_frame, text="Choose Folder", command=lambda: self.get_folder() ,font=choose_folder_font, bg="#707070", fg="white",borderwidth=0, cursor="hand2")
                self.choose_folder.bind("<Enter>", lambda event: self.choose_folder.config(bg="#505050"))
                self.choose_folder.bind("<Leave>", lambda event: self.choose_folder.config(bg="#707070"))
                self.selected_folder_label = Label(self.folder_frame, justify="left", text="",bg="white")

                self.folder_frame.pack()
                self.question_folder.pack(ipady="20")
                self.choose_folder.pack(ipadx="5", ipady="3")
                self.selected_folder_label.pack(ipady="10")


    #opens the file explorer to choose the folder to place the download
    def get_folder(self):
        #opens the file explorer
        folder = filedialog.askdirectory()
        self.selected_folder_label.config(text=folder)

        confirm_button_font = font.Font(size=12)

        #create the 'download button' if it is not created yet
        if (self.confirm_button is None):
            self.confirm_button = Button(self.button_frame, text="Download!", font=confirm_button_font,bg="red", fg="white", borderwidth=0, cursor="hand2")
            self.confirm_button.bind("<Enter>", lambda event: self.confirm_button.config(bg="#e60000"))
            self.confirm_button.bind("<Leave>", lambda event: self.confirm_button.config(bg="red"))

        self.confirm_button.config(command=lambda: self.download_video(folder))
        self.confirm_button.pack(ipady="5", ipadx="7", pady="30")


    # downloads the video when the user pressed the 'download' button
    def download_video(self, folder):
        app.download_frame.pack_forget()
        app.loading_page.pack_page()

        #does not download video if the selected video is a stream
        if (self.video["duration"] == "LIVE"):
            confirm_error = messagebox.showwarning("Unable to Download Streams", "Downloader unable to download streams")

            if (confirm_error == "ok"):
                app.loading_page.pack_forget()
                app.download_frame.pack()

        #downloads the video
        else:
            video_download_thread._callableArgs = [self.video, self.query, folder]
            app.loading_page.text_update = True

            try:
                path = video_download_thread.start()
            except:
                path = video_download_thread.restart()

            app.loading_page.check_running_thread(video_download_thread, app.download_finish_sc, [root, app.loading_page, self.page_found], "download", DownloadRequests.get_cached_progress)


    #hides all the children of the current NestedRadioButton that are displayed on the screen
    def unpack_children(self):
        for c in self.children:
            if (self.children[c] is not None):
                self.children[c].forget_options()
                self.children[c].unpack_children()


    #Hides the current NestedRadioButton
    def forget_options(self):
        self.button_frame.pack_forget()
        self.question_label.pack_forget()

        for o in self.options:
            o.pack_forget()

        if (self.confirm_button is not None):
            self.confirm_button.pack_forget()

        if (self.folder_frame is not None):
            self.folder_frame.pack_forget()




#Loading page to display when another thread is running
class LoadingPage:
    def __init__(self, master, message=""):
        self.max_growth = 20
        self.min_growth = 0
        self.master = master
        self.message = message
        self.load_page = ResizingCanvas(master, bg="white")
        self.load_rectangles = []
        self.make_loadbar()
        self.load_message_font = font.Font(size=11)
        self.load_message_text = StringVar()
        self.load_message_text.set("Loading...")
        self.load_message = Label(self.load_page, justify="left", textvariable=self.load_message_text, font=self.load_message_font,bg="white", fg="red")
        self.text_update = False


    #Creates the loadbar for the loading page, consisting of 10 bars
    def make_loadbar(self):
        x_center = self.load_page.width / 2
        y_center = self.load_page.height / 2

        rect_width = 4
        rect_spacing = 2
        rect_height = 30
        rect_colour = "red"


        x = x_center - (rect_width + rect_spacing) * 5
        y = y_center - int(rect_height / 2)

        for i in range(10):
            tmp_shape = self.load_page.create_rectangle(x, y, x + rect_width, y + rect_height,fill=rect_colour)
            self.load_rectangles.append({"shape": tmp_shape, "growth":"grow", "level":self.min_growth, "move":False, "cycle":1})
            x += rect_width + rect_spacing

        self.load_rectangles[0]["move"] = True


    #Displays the LoadingPage on the screen
    def pack_page(self):
        self.load_page.pack(fill="both")
        self.load_message.place(relx=0.5, rely=0.5, anchor="center")


    #Hides the LoadingPage
    def pack_forget(self):
        self.load_page.pack_forget()
        self.load_message.pack_forget()


    #Deletes the LoadingPage
    def destroy(self):
        self.load_page.destroy()
        self.load_message.destroy()


    #Updates the text displayed in the LoadingPage
    def update_text(self, func, args):
        text_to_update = func(*args)
        self.load_message_text.set(text_to_update)


    #Animates the loading bar of the LoadingPage and changes the text of the LoadingPage
    def animate(self, word_update_func = None, word_update_args=[]):
        if (not self.load_page.is_resizing):
            if (self.text_update):
                self.update_text(word_update_func, word_update_args)

            for i in range(len(self.load_rectangles)):
                x0, y0, x1, y1 = self.load_page.coords(self.load_rectangles[i]["shape"])

                if (self.load_rectangles[i]["move"]):
                    #stretches the current bar
                    if (self.load_rectangles[i]["growth"] == "grow"):
                        self.load_rectangles[i]["level"] += 1
                        y0 -= 1
                        y1 += 1

                        #moves the next bar once the current bar's is stretched halfway to its maximum size
                        if (self.load_rectangles[i]["level"] == self.max_growth/2):
                            next_i = i + 1
                            if (i == len(self.load_rectangles) - 1):
                                next_i = 0

                            self.load_rectangles[next_i]["move"] = True

                        #shrinks the current bar once it hits its maximum size
                        elif (self.load_rectangles[i]["level"] > self.max_growth):
                            self.load_rectangles[i]["growth"] = "shrink"

                    #shrink the current bar
                    elif (self.load_rectangles[i]["growth"] == "shrink"):
                        self.load_rectangles[i]["level"] -= 1
                        y0 += 1
                        y1 -= 1

                        #stops the bar from moving once it returns back to its minimum size
                        if (self.load_rectangles[i]["level"] < self.min_growth):
                            self.load_rectangles[i]["growth"] = "grow"
                            self.load_rectangles[i]["move"] = False

                    self.load_page.coords(self.load_rectangles[i]["shape"], x0, y0, x1, y1)
                    self.load_page.update()


    #Displays the LoadingPage on screen when a thread is running
    def check_running_thread(self, thread_class,func, args = [], key=None, word_update_func = None, word_update_args = [], delay = 25):
        #animate the loading bar when the thread is running
        if (thread_class._running):
            self.animate(word_update_func, word_update_args)
            app.after(delay, lambda: self.check_running_thread(thread_class, func, args, key, word_update_func, word_update_args))

        #runs the desired function once the thread has completed running
        else:
            #display the error message if the thread encountered an error
            if (thread_class._error):
                thread_class._error = True
                confirm_error = messagebox.showerror("An Error Has Occured", f"An error has unexpectedly occured during the proccess with the message:\n\n{processes[key]}\n\n- check if your internet is connected\n- restart the program")

                if (confirm_error == "ok"):
                    app.return_home(self, [displayed_search_pages, download_pages_lsts])
            else:
                thread_class.join()

                if (func is not None):
                    if (key is not None):
                        func(processes[key], *args)
                    else:
                        func(*args)




# The main application that is running
class Application(Frame):
    def __init__(self, master=None, word_wrap_thread=None):
        super().__init__(master)
        self.master = master
        self.opened_frame = None
        self.current_sc = ""
        self.pack()
        self.create_home_sc()
        self.word_wrap_thread = word_wrap_thread
        self.download_frame_created = False
        self.settings_opened = False
        self.settings_frame = None
        self.setting_search_applied = True
        self.current_search = ""


    #changes the text of inside of an Entry
    def set_text(self, root, text):
        root.delete(0,END)
        root.insert(0,text)


    #creates the home screen of the app
    def create_home_sc(self):
        self.search_frame = Frame(bg="white")
        self.search_frame.pack(expand="yes")

        self.opened_frame = self.search_frame
        self.current_sc = "home"

        #title of the app
        self.title_frame = Frame(self.search_frame, bg="white")
        self.first_title = Label(self.title_frame, text ='Youtube', font=("Arial", 30), bg="white", fg="red")
        self.second_title = Label(self.title_frame, text ='Downloader', font=("Arial", 30), bg="white")
        self.first_title.pack(side="left", expand="yes")
        self.second_title.pack(side="left", expand="yes")
        self.title_frame.grid(ipady=50)

        #search entry
        self.hm_search_entry_frame = Frame(self.search_frame, bg="black", relief="sunken")
        self.hm_search_entry = Entry(self.hm_search_entry_frame, width=70, font=("Times", 12))
        self.hm_search_entry.bind("<Return>", lambda event: self.search_video(self.hm_search_entry, "home"))
        self.hm_search_entry.bind("<Button-1>", lambda event, root=self.hm_search_entry_frame: root.config(bg="red"))
        self.hm_search_entry_frame.grid(ipady=1, ipadx=1)
        self.hm_search_entry.pack(expand="yes")

        #button to look for the results of the search
        search_bt_font = font.Font(size=12)
        self.search_bt = Button(self.search_frame, text="Search Video!", command=lambda: self.search_video(self.hm_search_entry, "home") ,font=search_bt_font, bg="#707070", fg="white", borderwidth=0, cursor="hand2")
        self.search_bt.bind("<Enter>", lambda event: self.search_bt.config(bg="#505050"))
        self.search_bt.bind("<Leave>", lambda event: self.search_bt.config(bg="#707070"))
        self.search_bt.grid(pady=10, ipadx=7, ipady=4)


    #Loads the images required for the results screen
    def create_results_sc(self,results, root):

        #load the first page of results
        self.load_page(root, results,0)


    # Loads a page of the results on the screen
    def load_page(self, master, results,page_num):
        #results
        outer_frame = Frame(master, bg="white")
        canvas = ResizingCanvas(outer_frame, bg="white")
        scrollbar = Scrollbar(outer_frame, orient="vertical", command=canvas.yview, bg="white")
        inner_frame = Frame(canvas, bg="white")

        displayed_search_pages[page_num] = ScrollFrame(master, outer_frame, canvas, inner_frame, scrollbar)

        selected_search = StringVar()

        search_lst = results


        #width and height of each image icon for the search results
        img_w = 150
        img_h = 100

        #number of search results per page
        search_per_page = int(setting_data["results/page"])
        pages, remaining_searches = divmod(len(results), search_per_page)

        if (not(remaining_searches)):
            pages -= 1

        start = None
        end = None

        #determine the searches to load from the results
        if (not(remaining_searches)):
            if (page_num <= pages):
                start = page_num * search_per_page
                end = (page_num + 1) * search_per_page
            else:
                print("PageError: Page Number Out of Bounds")

        else:
            if(page_num < pages):
                start = page_num * search_per_page
                end = (page_num + 1) * search_per_page
            elif (page_num == pages):
                start = page_num * search_per_page
                end = len(results)
            else:
                print("PageError: Page Number Out of Bounds")


        #creates the frames to display the search results
        if ((start is not None) and (end is not None)):
            for i in range(start, end):
                #frame to the search of each result
                temp_search_frame = Frame(displayed_search_pages[page_num].inner_frame, bg="white", cursor="hand2")
                temp_search_frame.bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                temp_search_frame.pack(fill="x", ipady=5, ipadx=sc_width)

                #image icon for each search result
                search_icon = Canvas(temp_search_frame, bg="white", width=img_w, height=img_h, highlightthickness=0)
                search_icon.bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                search_icon.create_image(0,0,anchor="nw",image=photo_lst[i])
                search_icon.pack(side="left", anchor="w", padx=10)


                #frame for the video attributes
                video_att_frame_lsts[i] = Frame(temp_search_frame, bg="white")
                video_att_frame_lsts[i].bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                video_att_frame_lsts[i].pack(side="left", anchor="w", ipadx=10, ipady=10)


                #time stamp for the duration of each video
                time_stamp = Label(search_icon)
                time_stamp.config(text= results[i]["duration"], bg="black", fg="white")
                time_stamp.bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                time_stamp.place(relx=1.0, rely=1.0,anchor="se")



                #video title
                video_title_font = font.Font(size = 12, weight="bold")
                video_title_text = FormatUtils.format_name(results[i]["title"])
                video_title = Label(video_att_frame_lsts[i], text=video_title_text, justify="left", bg="white", font=video_title_font)
                video_title.bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                video_title.pack(anchor="w")

                #Views and post date
                video_view_post_font = font.Font(size = 10)
                video_view_post = Label(video_att_frame_lsts[i], text=f"{results[i]['viewCount']['short']}   {results[i]['publishedTime']}", justify="left", bg="white", fg="#808080", font=video_view_post_font)
                video_view_post.bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                video_view_post.pack(anchor="w")

                #uploader
                uploader_text = FormatUtils.format_name(results[i]["channel"]["name"])
                uploader = Label(video_att_frame_lsts[i], text=uploader_text, justify="left", bg="white", fg="#808080")
                uploader.bind("<Button-1>", lambda event, prev_root = [self.result_frame, displayed_search_pages[page_num]], video=results[i], page_found = page_num: self.download_option_sc(prev_root,video, page_found))
                uploader.pack(anchor="w")


            #change the word items to be word wrapped
            vid_att_lsts = {}

            for i in video_att_frame_lsts:
                vid_att_lsts[i] = video_att_frame_lsts[i]

            self.word_wrap_thread.vid_att_lsts = vid_att_lsts

            #frame for pagination
            self.pagination_frame = Frame(displayed_search_pages[page_num].inner_frame, bg="white")
            self.pagination_frame.pack(anchor="nw", pady=30,fill="x")

            self.pagination = Frame(self.pagination_frame, bg="white")
            self.pagination.pack(side="left", anchor="w", padx=20)

            #display the back button if the current page is not the first page
            if (page_num):
                prev_page = Label(self.pagination, text=f"Back", bg="white", cursor="hand2")
                prev_page.bind("<Button-1>", lambda event, master = displayed_search_pages[page_num], results = results,page_num = page_num - 1: self.switch_page(event, master, results,page_num))
                prev_page.bind("<Enter>", lambda event: prev_page.config(fg="red"))
                prev_page.bind("<Leave>", lambda event: prev_page.config(fg="black"))
                prev_page.pack(side="left", expand="yes")


            #number of page numbers to display on screen at once
            pages_to_seek = 5
            #groups the pages into groups of 5
            no_of_page_groups, remaining_pages = divmod(len(results), pages_to_seek * search_per_page)

            #group of pages with less than 5 pages
            remaining_pages, not_r_pages_divisible = divmod(remaining_pages, search_per_page)


            if (not_r_pages_divisible):
                remaining_pages += 1

            #position of the current page
            page_group, current_page = divmod(page_num + 1, pages_to_seek)

            if (not(remaining_pages)):
                no_of_page_groups -= 1
                remaining_pages = pages_to_seek

            if(not(current_page)):
                page_group -= 1
                current_page = pages_to_seek

            start = pages_to_seek * page_group

            if (no_of_page_groups == page_group):
                end = start + remaining_pages
            else:
                end = pages_to_seek * (page_group + 1)

            #display the page numbers of the current group of pages
            for i in range(start, end):
                if (i + 1 == current_page + pages_to_seek * page_group):
                    page_label = Label(self.pagination, text=f"{i + 1}", bg="white", fg="red", cursor="hand2", underline=0)
                else:
                    page_label = Label(self.pagination, text=f"{i + 1}", bg="white", cursor="hand2")
                    page_label.bind("<Enter>", lambda event, highlight_pg = page_label: highlight_pg.config(fg="red"))
                    page_label.bind("<Leave>", lambda event, highlight_pg = page_label: highlight_pg.config(fg="black"))

                page_label.pack(side="left", expand="yes")
                page_label.bind("<Button-1>", lambda event, master = displayed_search_pages[page_num], results = results,page_num = i: self.switch_page(event, master, results,page_num))


            #display the next button if the current page is not the last page
            if (page_num < pages):
                next_page = Label(self.pagination, text=f"Next", bg="white", cursor="hand2")
                next_page.bind("<Button-1>", lambda event, master = displayed_search_pages[page_num], results = results,page_num = page_num + 1: self.switch_page(event, master, results,page_num))
                next_page.bind("<Enter>", lambda event: next_page.config(fg="red"))
                next_page.bind("<Leave>", lambda event: next_page.config(fg="black"))
                next_page.pack(side="left", expand="yes")

            self.loading_page.pack_forget()
            self.heading_frame.pack(anchor="nw", fill="x")
            displayed_search_pages[page_num].pack_frame()


    # When the user switches from 1 page of the search results to another page in the search results
    def switch_page(self, event, master ,results,page_num):
        master.pack_forget()

        #load the page from the dictionary if it is already loaded
        if(page_num in displayed_search_pages):
            displayed_search_pages[page_num].pack_frame(page_num)
        else:
            self.load_page(self.result_frame, results, page_num)


    #searches the video and shows the frames to be displayed
    def search_video(self, entry, current_sc, dl_pg_key=None):
        self.setting_search_applied = True
        global displayed_search_pages

        #get the text value of the search entry
        try:
            search = entry.get()
        except:
            search = entry

        #determines if the search entry is a link to a youtube video
        valid_youtube_link = DLUtils.valid_yt_link(search)

        #creates the frame for the results if not created yet
        if (current_sc == "home"):
            prev_root = [self.search_frame]
            self.search_frame.pack_forget()
            self.result_frame = Frame(bg="white")

            self.create_heading(self.result_frame, [displayed_search_pages])

        elif (current_sc == "search"):
            key = list(displayed_search_pages.keys())[0]
            prev_root = [self.result_frame, displayed_search_pages[key]]

        elif (current_sc == "download"):
            if (not displayed_search_pages):
                prev_root = [self.search_frame]
            else:
                key = list(displayed_search_pages.keys())[0]
                prev_root = [self.result_frame, displayed_search_pages[key]]

        elif (current_sc == "finish"):
            prev_root = [self.finish_download_frame]


        #jumps to the download frame if the search entry is a valid youtube video link
        if (valid_youtube_link):
            if (current_sc == "download"):
                for p in download_pages_lsts:
                    download_pages_lsts[p].destroy_frame()

                self.clear_search("displayed_search_pages")
                self.download_frame.pack_forget()


            self.download_option_sc(prev_root,search, 0, is_link=True)

        #displays the search frame listing the search results
        else:
            self.current_search = search
            self.opened_frame = self.result_frame
            self.current_sc = "search"
            self.loading_page = LoadingPage(self.master, "loading...")
            self.loading_page.pack_page()

            search_video_thread._callableArgs = [search, int(setting_data["results/search"])]
            search_video_thread._running = True
            try:
                results = search_video_thread.start()
            except:
                results = search_video_thread.restart()


            if (current_sc == "home"):
                self.result_frame.pack(anchor="nw", fill="both")
                self.heading_frame.pack_forget()

            else:
                #forget all the pages of the previous search
                for p in displayed_search_pages.values():
                    p.destroy_frame()

                for p in download_pages_lsts.values():
                    p.destroy_frame()

                self.clear_search()

                #forget all the previous download pages
                if (current_sc == "download" or current_sc == "finish"):
                    for p in download_pages_lsts.values():
                        p.destroy_frame()

                    self.download_frame.pack_forget()

                    if (current_sc == "finish"):
                        self.finish_download_frame.pack_forget()

                    self.result_frame.pack(anchor="nw", fill="both")

            self.loading_page.check_running_thread(search_video_thread, self.create_results_sc, [self.result_frame], "search")


    #creates the heading search bar
    def create_heading(self, root, scrollframe = None, current_sc = "search"):
        #heading frame
        self.heading_frame = Frame(root, bg="white")
        self.heading_frame.pack(anchor="nw", fill="x")

        #title of the program
        program_title_frame = Frame(self.heading_frame, bg="white", cursor="hand2")
        program_title_frame.bind("<Button-1>", lambda event, root=root: self.return_home(root, scrollframe))
        first_program_title = Label(program_title_frame, text = 'Youtube', font=("Helvetica", 13), anchor="w", bg="white", fg="red")
        first_program_title.bind("<Button-1>", lambda event, root=root: self.return_home(root, scrollframe))
        second_program_title = Label(program_title_frame, text = 'Downloader', font=("Helvetica", 13), anchor="w", bg="white")
        second_program_title.bind("<Button-1>", lambda event, root=root: self.return_home(root, scrollframe))
        first_program_title.pack(side="left", expand="yes")
        second_program_title.pack(side="left", expand="yes")
        program_title_frame.pack(side="left", padx=20)

        #search entry
        search_entry_frame = Frame(self.heading_frame, bg="black", relief="sunken")
        search_entry = Entry(search_entry_frame, width=60, font=("Times", 12))
        search_entry.bind("<Return>", lambda event, current_sc = current_sc: self.search_video(search_entry, current_sc))
        search_entry.bind("<Button-1>", lambda event, root=search_entry_frame: root.config(bg="red"))
        search_entry_frame.pack(side="left", padx=10, pady=30, ipadx=1,ipady=1,fill="x")
        search_entry.pack(expand="yes")


    #clears all the previous remembered pages that the app has been to
    def clear_search(self, keep_pages = ""):
        self.word_wrap_thread.terminate()

        global video_att_frame_lsts
        video_att_frame_lsts = {}

        #change the word items to be word wrapped
        vid_att_lsts = {}

        for i in video_att_frame_lsts:
            vid_att_lsts[i] = video_att_frame_lsts[i]

        self.word_wrap_thread.vid_att_lsts = vid_att_lsts
        self.word_wrap_thread._running = True


        #reset all global saved variables
        global photo_lst
        global search_lst
        global displayed_search_pages
        global download_pages_lsts

        search_lst = []

        if (not (keep_pages == "download_pages_lsts")):
            download_pages_lsts = {}

        if (not (keep_pages == "displayed_search_pages")):
            photo_lst = {}
            displayed_search_pages = {}


    #Gets the video attributes for the selected video
    def download_option_sc(self, prev_root,video, page_found, is_link=False):
        prev_root[0].pack_forget()

        #create the download frame if it has not been created yet
        if (not self.download_frame_created):
            self.download_frame = Frame(bg="white")

        self.opened_frame = self.download_frame
        self.current_sc = "download"
        self.download_frame.pack(anchor="nw", fill="both")

        #create the scrollable frame for the download
        outer_frame = Frame(self.download_frame, bg="white")
        canvas = ResizingCanvas(outer_frame, bg="white")
        scrollbar = Scrollbar(outer_frame, orient="vertical", command=canvas.yview, bg="white")
        inner_frame = Frame(canvas, bg="white")


        if (not is_link):
            key = video["id"]
        else:
            key = -1

        #get the video attributes for the selected video if the app has not been to the download frame yet
        if (key not in download_pages_lsts.keys() or key == -1):
            if (not is_link):
                download_pages_lsts[key] = ScrollFrame(self.download_frame, outer_frame, canvas, inner_frame, scrollbar)
                link = video["link"]
                time = video["duration"]
                date_posted = video["publishedTime"]
                title = FormatUtils.format_name(video["title"])
                uploader = FormatUtils.format_name(video["channel"]["name"])

                video_att = {"key":key, "link":link, "time":time, "date posted":date_posted, "title":title, "uploader":uploader}

                meta_data_thread._callableArgs = [link]

                self.loading_page = LoadingPage(self.master, "loading...")
                self.loading_page.pack_page()

                try:
                    meta = meta_data_thread.start()
                except:
                    meta = meta_data_thread.restart()

                self.loading_page.check_running_thread(meta_data_thread, self.choose_download, [video, video_att, page_found, is_link, prev_root], "meta")

            else:
                download_pages_lsts[key] = ScrollFrame(self.download_frame, outer_frame, canvas, inner_frame, scrollbar)
                link = video

                self.loading_page = LoadingPage(self.master, "loading...")
                self.loading_page.pack_page()
                video_att = {"key":key, "link":link}

                meta_data_thread._callableArgs = [link]

                try:
                    meta = meta_data_thread.start()
                except:
                    meta = meta_data_thread.restart()

                self.loading_page.check_running_thread(meta_data_thread, self.choose_download, [video, video_att, page_found, is_link, prev_root], "meta")


        #reload the download frame if the frame has been remembered
        else:
            download_pages_lsts[key].pack_frame(key)


    #Displays the download frame for the selected video
    def choose_download(self, meta, video, video_att, page_found, is_link, prev_page):
        if (not is_link):
            key = video_att["key"]
            link = video_att["link"]
            time = video_att["time"]
            date_posted = video_att["date posted"]
            title = video_att["title"]
            uploader = video_att["uploader"]
            video_attributes = {"Views": video["viewCount"]["text"]}
        else:
            key = video_att["key"]
            link = video_att["link"]
            meta_data_thread
            time = FormatUtils.format_time(meta["duration"])
            title = meta["title"]
            uploader = meta["uploader"]
            date_posted = FormatUtils.format_date(str(meta["upload_date"]))
            video_attributes = {"Views":FormatUtils.format_count(str(meta["view_count"]), '')}

            video = {"id": meta["id"], "link": link, "title": title, "channel": {"name": uploader}, "duration": time, "publishedTime": date_posted, "viewCount": {"text": video_attributes["Views"]}}



        try:
            video_attributes["Likes"] = FormatUtils.format_count(str(meta["like_count"]), '')
        except:
            pass

        video_attributes["Duration"] = time
        video_attributes["Date Posted"] = date_posted
        video_attributes["Uploader"] = FormatUtils.format_name(uploader)
        video_attributes["Link"] = link

        #create the heading for the download frame if the frame has just been created
        if(not self.download_frame_created):
            self.create_heading(self.download_frame, [download_pages_lsts, displayed_search_pages], "download")
            self.download_frame_created = True

        download_pages_lsts[key].pack_frame()

        #displays the back button to go back to the previous page
        back_button = Button(download_pages_lsts[key].inner_frame, text="← Back", command=lambda: self.return_to_prev_pg([self.download_frame, download_pages_lsts[key]], prev_page, "search", page_found,{"expand":"yes"}) ,bg="#707070", fg="white",borderwidth=0, cursor="hand2")
        back_button.bind("<Enter>", lambda event, back_button = back_button: back_button.config(bg="#505050"))
        back_button.bind("<Leave>", lambda event, back_button = back_button: back_button.config(bg="#707070"))
        back_button.pack(anchor="nw", padx=10, ipadx=5, ipady=3)

        if (not is_link):
            thumbnail = video["thumbnails"][-1]["url"]
        else:
            thumbnail = meta["thumbnail"]

        video_frame = Frame(download_pages_lsts[key].inner_frame,bg="white")
        video_frame.pack(fill="x", expand=True, padx=150, pady=20)

        #width and height for the image
        img_w = 200
        img_h = 125

        #get the thumbnail for the selected video
        resized_image = FormatUtils.process_image(thumbnail, img_w, img_h)
        photo_lst[f"d{key}"] = ImageTk.PhotoImage(resized_image)
        resized_image  = photo_lst[f"d{key}"]

        #image icon for the selected search result
        search_icon = Canvas(video_frame, bg="white", width=img_w, height=img_h, highlightthickness=0)
        search_icon.create_image(0,0,anchor="nw",image=resized_image )
        search_icon.pack(padx=20, pady=10)

        #time stamp on the search icon
        time_stamp = Label(search_icon)
        time_stamp.config(text= time, bg="black", fg="white")
        time_stamp.place(relx=1.0, rely=1.0,anchor="se")

        #attributes for the video
        video_attributes_frame = Frame(video_frame, bg="white")
        video_attributes_frame.pack()

        #video title
        video_title_frame = Frame(video_attributes_frame, bg="white")
        video_title_frame.pack()

        video_title_font = font.Font(size = 12, weight="bold")
        video_title_text = title
        video_title = Label(video_title_frame, text=video_title_text, justify="left", bg="white", font=video_title_font)
        video_title.pack()

        #wrap the text in the title and the video attributes
        word_wrap_lst = {"title": video_title_frame}


        video_att_font = font.Font(size = 10)

        #display the search attributes of the frame
        for a in video_attributes:
            video_att_frame = Frame(video_attributes_frame, bg="white")
            video_att_frame.pack()

            video_att_heading = Label(video_att_frame, text=f"{a}: ",bg="white", fg="#606060", font=video_att_font)
            video_att_heading.pack(side="left", anchor="nw",expand="yes")

            video_att = Label(video_att_frame, text=video_attributes[a], justify="left", bg="white", fg="#808080", font=video_att_font)

            #allow the user to be able copy the video link to their clipboard
            if (a == "Link"):


                video_att.config(fg="#4da6ff", cursor="hand2")
                video_att.bind("<Button-1>", lambda event, link=video_attributes[a]: self.copy_link(link))
                video_att.bind("<Enter>", lambda event, label = video_att: label.config(fg="#0080ff"))
                video_att.bind("<Leave>", lambda event, label = video_att: label.config(fg="#4da6ff"))

            video_att.pack(side="left", anchor="nw", expand="yes")

            word_wrap_lst[f"{a} {video['id']}"] = video_att_frame

        self.loading_page.pack_forget()

        self.word_wrap_thread.terminate()
        self.word_wrap_thread.extra_length = -200
        self.word_wrap_thread.vid_att_lsts = word_wrap_lst
        self.word_wrap_thread._running = True


        #all the video formats for download
        download_formats = meta["formats"]
        available_formats = DLUtils.get_available_formats(download_formats)
        video_codes  = [YtDownloadFormat.mp4_144p.value, YtDownloadFormat.mp4_240p.value,
                        YtDownloadFormat.mp4_360p.value, YtDownloadFormat.mp4_480p.value,
                        YtDownloadFormat.mp4_720p.value, YtDownloadFormat.mp4_1080p.value,
                        YtDownloadFormat.mp4_640x360.value, YtDownloadFormat.mp4_1280x720.value,
                        YtDownloadFormat.gp3_176x144.value, YtDownloadFormat.gp3_320x240.value,
                        YtDownloadFormat.flv.value]

        avail_video_formats = []

        #find the available video formats to download for the selected video
        for c in video_codes:
            if (c in available_formats):
                avail_video_formats.append(c)

        video_formats = DLUtils.format_filetype(avail_video_formats)

        #audio formats to download video
        available_audio_formats = {audio_filetypes["mp3"]:None, audio_filetypes["m4a"]:None, "ogg":None, audio_filetypes["aac"]:None,
                                   audio_filetypes["wav"]:None, audio_filetypes["opus"]: None, audio_filetypes["flac"]: None, "don't care":None}

        available_video_formats = {}

        for v in video_formats:
            available_video_formats[video_formats[v]] = None

        available_video_formats["avi"] = None
        available_video_formats["webm"] = None
        available_video_formats["mkv"] = None
        available_video_formats["don't care"] = None


        #frame to contain all of the questions
        dl_master = download_pages_lsts[key].inner_frame


        #radio buttons for download format
        download_format_frame = Frame(dl_master)
        download_question_label = Label(download_format_frame, justify="left", bg="light blue")

        download_questions = NestedRadioButton(dl_master,"Choose a Download Option:",
            {"Audio":NestedRadioButton(dl_master,"Choose a download quality",
                {"best quality": NestedRadioButton(dl_master,"Choose a Format",available_audio_formats, video, page_found),
                    "worst quality": NestedRadioButton(dl_master,"Choose a Format",available_audio_formats, video, page_found)}),
             "Video":NestedRadioButton(dl_master,"Choose a download quality",
                {"best quality": NestedRadioButton(dl_master,"Do you want audio to be included?",
                    {"Yes! Download video with audio.":NestedRadioButton(dl_master,"Choose an audio download quality",
                        {"best quality": NestedRadioButton(dl_master,"Choose a Video Download Format",available_video_formats, video, page_found),
                            "worst quality": NestedRadioButton(dl_master,"Choose a Video Download Format",available_video_formats, video, page_found)}),
                     "No! Download video without audio.":NestedRadioButton(dl_master,"Choose a Video Download Format",available_video_formats, video, page_found)}),
                         "worst quality": NestedRadioButton(dl_master,"Do you want audio to be included?",
                    {"Yes! Download video with audio.":NestedRadioButton(dl_master,"Choose an audio download quality",
                        {"best quality": NestedRadioButton(dl_master,"Choose a Video Download Format",available_video_formats, video, page_found),
                         "worst quality": NestedRadioButton(dl_master,"Choose a Video Download Format",available_video_formats, video, page_found)}),
                     "No! Download video without audio.":NestedRadioButton(dl_master,"Choose a Video Download Format",available_video_formats, video, page_found)})})})

        download_questions.make_button()


    #copy video link to the clipboard in the download frame
    def copy_link(self, link):
        FormatUtils.copy_text(link)
        messagebox.showinfo("Link Copied", "The link to the video has been successfully copied to the Clipboard")


    #returns from the previous page back to the home screen
    def return_home(self, root, lst_of_scrollpageslst = None):
        #destroys all the remembered pages
        if (lst_of_scrollpageslst is not None):

            for scrollpageslst in lst_of_scrollpageslst:
                for s in scrollpageslst.values():
                    s.destroy_frame()

        #clears all the remembered data
        self.clear_search()
        root.destroy()


        self.search_frame.pack(expand="yes")
        self.set_text(self.hm_search_entry, "")

        self.opened_frame = self.search_frame
        self.current_sc = "home"

        self.hm_search_entry_frame.config(bg="black")


    #returns to previous page
    def return_to_prev_pg(self, current_pages, pages_to_load, sc_to_load,page_num=0, pack_kwargs={}, clear=False):
        self.settings_opened = False
        #hides the frames to be forgotten
        for p in current_pages:
            p.pack_forget()

        if (clear):
            for p in download_pages_lsts:
                download_pages_lsts[p].destroy_frame()

            self.clear_search("displayed_search_pages")

        #displays all the frames to be displayed
        if (self.setting_search_applied or len(pages_to_load) == 1):
            self.opened_frame = pages_to_load[0]
            self.current_sc = sc_to_load
            for p in pages_to_load:
                try:
                    p.pack_frame(page_num)
                except:
                    p.pack(**pack_kwargs)

        else:
            for p in displayed_search_pages:
                displayed_search_pages[p].destroy_frame()

            self.clear_search("download_pages_lsts")
            self.search_video(self.current_search, self.current_sc)



    #page to display when the download is successful
    def download_finish_sc(self, download_path, root, prev_page,page_found):
        prev_page.pack_forget()
        self.loading_page.text_update = False
        self.finish_download_frame = Frame(bg="white")
        self.opened_frame = self.finish_download_frame
        self.current_sc = "finish"
        self.finish_download_frame.pack(expand="yes", fill="both")
        self.create_heading(self.finish_download_frame, [download_pages_lsts, displayed_search_pages],current_sc="finish")

        self.finish_download_status = Frame(self.finish_download_frame, bg="white")
        self.finish_download_status.pack()

        finish_download_font = font.Font(size=16, weight="bold")
        self.finish_download_title = Label(self.finish_download_status, text="Download Successful", justify="left", font=finish_download_font,bg="white")
        self.finish_download_title.pack(fill="x")

        #path of where the download is located
        finish_download_font = font.Font(size=12)
        self.finish_download_sentence = Label(self.finish_download_status, text="Your Download has finished and the file is located at:", justify="left", font=finish_download_font,bg="white")
        self.finish_download_sentence.pack()

        self.finish_download_sentence = Label(self.finish_download_status, text=download_path, justify="left",bg="white")
        self.finish_download_sentence = Label(self.finish_download_status, text=download_path, justify="left",bg="white", fg="#4da6ff")
        self.finish_download_sentence.config(fg="#4da6ff", cursor="hand2")
        self.finish_download_sentence.bind("<Button-1>", lambda event, filepath = download_path: self.open_explorer(filepath))
        self.finish_download_sentence.bind("<Enter>", lambda event, label = self.finish_download_sentence: label.config(fg="#0080ff"))
        self.finish_download_sentence.bind("<Leave>", lambda event, label = self.finish_download_sentence: label.config(fg="#4da6ff"))
        self.finish_download_sentence.pack()

        self.finish_button_frame = Frame(self.finish_download_frame, bg="white")
        self.finish_button_frame.pack()

        #button for the user to return to the previous page
        if (displayed_search_pages):
            self.return_prev_page = Button(self.finish_button_frame, text="Return to Previous Page", command=lambda:self.return_to_prev_pg([self.finish_download_frame], [self.result_frame, displayed_search_pages[page_found]], "search",page_found, clear=True),bg="red", fg="white", borderwidth=0, cursor="hand2")

        else:
            self.return_prev_page = Button(self.finish_button_frame, text="Return Home", command=lambda:self.return_home(self.finish_download_frame, [download_pages_lsts, displayed_search_pages]),bg="red", fg="white", borderwidth=0, cursor="hand2")

        self.return_prev_page.bind("<Enter>", lambda event: self.return_prev_page.config(bg="#e60000"))
        self.return_prev_page.bind("<Leave>", lambda event: self.return_prev_page.config(bg="red"))
        self.return_prev_page.pack(side="left", expand="yes", padx=20, pady=20, ipadx=5, ipady=3)

        #button for the user to return back to the download page of the selected video
        self.return_download_page = Button(self.finish_button_frame, text="Return to Download Page",command=lambda:self.return_to_prev_pg([self.finish_download_frame], [self.download_frame], "download"),bg="red", fg="white", borderwidth=0, cursor="hand2")
        self.return_download_page.bind("<Enter>", lambda event: self.return_download_page.config(bg="#e60000"))
        self.return_download_page.bind("<Leave>", lambda event: self.return_download_page.config(bg="red"))
        self.return_download_page.pack(side="left", expand="yes",padx=20, pady=20, ipadx=5, ipady=3)


        word_wrap_lst = {"finish":self.finish_download_status}

        #wrap the text
        self.word_wrap_thread.terminate()
        self.word_wrap_thread.extra_length = -200
        self.word_wrap_thread.vid_att_lsts = word_wrap_lst
        self.word_wrap_thread._running = True


    #creates the settings page
    def settings_sc(self):
        if (not self.settings_opened and not video_download_thread._running and not search_video_thread._running and not meta_data_thread._running):
            self.opened_frame.pack_forget()
            self.settings_opened = True

            self.settings_frame = Frame(bg="white")
            self.settings_frame.pack(expand="yes")
            settings_font = font.Font(size=16, weight="bold")
            self.settings_title = Label(self.settings_frame, text="Settings", justify="left", font=settings_font,bg="white")
            self.settings_title.pack()

            #entry and slider to change the number of results fround per search
            self.settings_search_frame = Frame(self.settings_frame, bg="white")
            self.settings_search_frame.pack()
            settings_font = font.Font(size=12)
            self.settings_search_sbt = Label(self.settings_search_frame, text="Number of Results Found Per Search", justify="left", font=settings_font,bg="white")
            self.settings_search_sbt.pack()

            self.results_per_search = IntVar()
            self.results_per_search.set(int(setting_data["results/search"]))
            self.settings_search_entry_fr = Frame(self.settings_search_frame, bg="black", relief="sunken")
            self.settings_search_entry = Entry(self.settings_search_entry_fr, width=3)
            self.set_text(self.settings_search_entry, setting_data["results/search"])
            self.settings_search_entry_fr.pack(ipady=1, ipadx=1)
            self.settings_search_entry.bind("<Button-1>", lambda event, root=self.settings_search_entry_fr: root.config(bg="red"))
            self.settings_search_entry.bind("<Return>", lambda event: self.entry_change_setting(self.settings_search_entry_fr,"results/search", self.settings_search_entry,self.results_per_search))
            self.settings_search_entry.pack(expand="yes")
            self.settings_search_scale = Scale(self.settings_search_frame, variable = self.results_per_search ,  from_ = 1, to = 100,  command=lambda text, root = self.settings_search_entry:self.set_text(root, text),orient = "horizontal", bg="white", highlightbackground="white")
            self.settings_search_scale.pack()

            #entry and slider to change the number of search results to display per page
            self.settings_page_frame = Frame(self.settings_frame, bg="white")
            self.settings_page_frame.pack()
            self.settings_page_sbt = Label(self.settings_page_frame, text="Number of Results Displayed Per Page", justify="left", font=settings_font,bg="white")
            self.settings_page_sbt.pack()

            self.results_per_page = IntVar()
            self.results_per_page.set(int(setting_data["results/page"]))
            self.settings_page_entry_fr = Frame(self.settings_search_frame, bg="black", relief="sunken")
            self.settings_page_entry = Entry(self.settings_page_entry_fr, width=3)
            self.set_text(self.settings_page_entry, setting_data["results/page"])
            self.settings_page_entry_fr.pack(ipady=1, ipadx=1)
            self.settings_page_entry.pack(expand="yes")
            self.settings_page_entry.bind("<Button-1>", lambda event, root=self.settings_page_entry_fr: root.config(bg="red"))
            self.settings_page_entry.bind("<Return>", lambda event: self.entry_change_setting(self.settings_page_entry_fr, "results/page", self.settings_page_entry,self.results_per_page))
            self.settings_page_scale = Scale(self.settings_page_frame, variable = self.results_per_page,  from_ = 1, to = 100, command=lambda text, root = self.settings_page_entry:self.set_text(root, text) ,orient = "horizontal", bg="white", highlightbackground="white")
            self.settings_page_scale.pack()

            #the submit button for the setting changes and the closed button for the settings page
            self.settings_submit_frame = Frame(self.settings_frame, bg="white")
            self.settings_submit_frame.pack(anchor="sw")
            self.settings_submit_apply = Button(self.settings_frame, text="Apply",bg="red", fg="white", command=lambda:self.apply_setting_changes({"results/search":self.results_per_search.get(), "results/page":self.results_per_page.get()}),borderwidth=0, cursor="hand2")
            self.settings_submit_apply.bind("<Enter>", lambda event: self.settings_submit_apply.config(bg="#e60000"))
            self.settings_submit_apply.bind("<Leave>", lambda event: self.settings_submit_apply.config(bg="red"))
            self.settings_submit_close = Button(self.settings_frame, text="Close",bg="red", fg="white", command=lambda:self.return_to_prev_pg([self.settings_frame], [self.opened_frame],self.current_sc,pack_kwargs={"expand":"yes"}),borderwidth=0, cursor="hand2")
            self.settings_submit_close.bind("<Enter>", lambda event: self.settings_submit_close.config(bg="#e60000"))
            self.settings_submit_close.bind("<Leave>", lambda event: self.settings_submit_close.config(bg="red"))
            self.settings_submit_close.pack(side="right", padx=10, pady=10, ipadx=5, ipady=3)
            self.settings_submit_apply.pack(side="right", padx=10, pady=10, ipadx=5, ipady=3)


    #opens the file explorer when the user clicks on the path of the finish download
    def open_explorer(self, filepath):
        dir = os.path.dirname(filepath)
        os.startfile(dir)

    #when the user changes the entry of the settings
    def entry_change_setting(self,entry_frame,key, entry, var):
        value = entry.get()
        formatted_value = FormatUtils.format_settings(key, value)
        var.set(formatted_value)
        self.set_text(entry, formatted_value)
        entry_frame.config(bg="black")


    #when the changes in the settings are applied
    def apply_setting_changes(self, lst_of_vars):
        global setting_data
        setting_data = lst_of_vars
        setting_file.change_data(setting_data)

        confirm_setting = messagebox.showinfo("Setting Changes", "Changes to Settings have benn Succesfully Applied")

        if (confirm_setting == "ok"):
            self.close_settings()


    #when the user closes the settings page
    def close_settings(self):
        if (self.current_sc == "home"):
            kwargs = {"expand":"yes"}
        else:
            kwargs = {}

        self.return_to_prev_pg([self.settings_frame], [self.opened_frame],self.current_sc,pack_kwargs=kwargs)

        self.setting_search_applied = False

        if (self.current_sc == "search"):
            self.search_video(self.current_search, self.current_sc)



#wraps text sections based on the adjustment to the app window
class WordWrap():
    def __init__(self, root, vid_att_lsts):
        super().__init__()
        self.master = root
        self.vid_att_lsts = vid_att_lsts
        self.extra_length = -260
        self._running = True

    #stops checking to wrap texts
    def terminate(self):
        self._running = False

    #wraps the selected text
    def wrap_search_text(self):
        if (self._running):
            self.master.bind("<Configure>", lambda event: self.wrap_text(event))

    #wraps the text in the children widgets of the frames selected
    def wrap_text(self, event):
        window_width = self.master.winfo_width()
        wrap_length = window_width + self.extra_length

        for r in self.vid_att_lsts.values():
            for child in r.winfo_children():
                child.config(wraplength = wrap_length)



#restartable thread
class ProcessThread(threading.Thread):
    def __init__(self, target, args, key, return_value=False):
        self._startSignal = threading.Event()
        self._oneRunFinished = threading.Event()
        self._finishIndicator = False
        self._callable = target
        self._callableArgs = args
        self.key = key
        self.return_value = return_value
        self._running = False
        self._error = False

        threading.Thread.__init__(self)


    def restart(self):
        self._startSignal.set()
        self._running = True


    def run(self):
        self.restart()
        while(True):
            # wait until we should process
            self._startSignal.wait()

            self._startSignal.clear()

            if(self._finishIndicator):# check, if we want to stop
                self._oneRunFinished.set()
                return

            self._running = True
            # call the threaded function
            if (self.return_value):
                try:
                    processes[self.key] = self._callable(*self._callableArgs)
                except Exception as e:
                    exception_lst = traceback.format_exception(type(e), e, e.__traceback__)
                    exception_str = "".join(exception_lst)

                    for e in exception_lst:
                        exception_str += e

                    self._running = False
                    self._error = True
                    processes[self.key] = f"{e}\n\n{exception_str}"
            else:
                try:
                    self._callable(*self._callableArgs)
                except Exception as e:
                    exception_lst = traceback.format_exception(type(e), e, e.__traceback__)
                    exception_str = "".join(exception_lst)

                    self._running = False
                    self._error = True
                    processes[self.key] = f"{e}\n\n{exception_str}"

            # notify about the run's end
            self._running = False
            self._oneRunFinished.set()


    def join(self):
        self._oneRunFinished.wait()
        self._oneRunFinished.clear()


    def finish(self):
        self._finishIndicator = True
        self.restart()
        self.join()



# search_videos(search_query, no_of_searches): Searches and formats the
#   needed data for the videos results
def search_videos(search_query: str, no_of_searches: int):
    results = search_youtube_video(search_query, no_of_searches)

    #width and height of each image icon for the search results
    img_w = 150
    img_h = 100
    result_len = len(results)

    #load all the images for the search results
    for i in range(result_len):
        thumbnails = results[i]["thumbnails"]

        resized_image = FormatUtils.process_image(thumbnails[-1]["url"], img_w, img_h)
        FormatUtils.load_image(resized_image, photo_lst, i)

    return results


# run_main(): Runs the main app
def run_main(make_txt_setup: bool = False):
    if (root is not None):
        global setting_data
        global setting_file

        #re-read the data from the setup file
        if (make_txt_setup):
            file_dir = os.getcwd()
            setting_file = SetupFile("setup.txt", file_dir)

        setting_data = setting_file.get_data()

        root.config(menu=menu_bar, bg="white")

        #start the word wrap
        search_wrap_thread.start()

        #start the main app
        app.mainloop()




if (__name__ != "__main__"):
    video_att_lsts = {}

    for v in video_att_frame_lsts:
        video_att_lsts[v] = video_att_frame_lsts[v]


    # current file path of this file
    file_path = os.path.realpath(__file__)
    file_dir = os.path.dirname(file_path)


    #read the data from the setup file
    setting_file = SetupFile("setup.txt", file_dir)

    #create the root window for the app
    root = Tk()
    root.title("Youtube Downloader")
    sc_width = int(root.winfo_screenwidth() / 2)
    sc_height = int(root.winfo_screenheight() / 2)
    root.geometry(f"{sc_width}x{sc_height}+-7+0")


    #wrap text
    word_wrap = WordWrap(root, video_att_lsts)

    #threads to search, download, or get meta data from videos
    search_wrap_thread = threading.Thread(target=word_wrap.wrap_search_text, args=[])
    video_download_thread = ProcessThread(target=DownloadRequests.prepare_download, args=[None, None, None], key="download", return_value=True)
    search_video_thread = ProcessThread(target=search_videos, args=[None, None], key="search", return_value=True)
    meta_data_thread = ProcessThread(target=DownloadRequests.get_metadata, args=[None], key="meta", return_value=True)
    video_download_thread.daemon = True
    search_video_thread.daemon = True
    meta_data_thread.daemon = True

    #create the app
    app = Application(master=root, word_wrap_thread=word_wrap)


    #menu bar
    menu_bar = Menu(root, activebackground="#ff6666", bg="#ffffff", cursor="hand2")

    #settings menu
    settings = Menu(root, tearoff=0, activebackground="#ff3333", bg="white", fg="black",cursor="hand2")
    settings.add_command(label="Settings", command=lambda:app.settings_sc())

    settings.add_separator()

    settings.add_command(label="Exit", command=root.quit)
    menu_bar.add_cascade(label="File", menu=settings)


    #icon photo
    try:
        root.iconbitmap(f"{file_dir}\\icon.ico")
    except:
        pass
