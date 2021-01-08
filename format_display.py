import codecs, requests, asyncio
from PIL import ImageTk, Image
from io import BytesIO
import pyperclip

import setup


'''
format_count(count,unit) Formats 'count' to include its beginning and its number
    base
format_count: str, str -> strip
'''
def format_count(count, unit):

    if(count.isnumeric()):
        nat_count = int(count)
        num_of_digits = len(count)

        #number bases for the count
        unit_lst = ["K", "M", "B", "T", "Quad", "Quin", "Se", "Sep", "Oct", "N", "D"]

        #simply display the number if the number is less than 1000
        if (nat_count < 1000):
            if (nat_count == 1 and not (unit == "")):
                unit = unit[:-1]
            return count + " " + unit

        #display the number with its base
        elif (num_of_digits % 3 == 1):
            first_num = count[0]
            second_num = count[1]

            if (second_num == "0"):
                format = f"{first_num} {unit_lst[int(num_of_digits/3) - 1]}"
            else:
                format =  f"{first_num}.{second_num} {unit_lst[int(num_of_digits/3) - 1]}"

        elif(num_of_digits % 3 == 2):
            format = f"{count[0:2]} {unit_lst[int(num_of_digits/3) - 1]}"
        elif(not (num_of_digits % 3)):
            format = f"{count[0:3]} {unit_lst[int(num_of_digits/3) - 1]}"
        else:
            format = count

        return format + " " + unit

    #if the count >= 10 ^ 34, than simply display the number
    else:
        return count


'''
format_name(name) Changes all the UTF-8 characters in 'name' to its respective
    special character
format_name: str -> str
'''
def format_name(name):
    name = codecs.decode(name, "unicode_escape")
    return name


'''
format_time(time) Produces a string that divides 'time' into days, hours,
    minutes and seconds
format_time: int -> str
'''
def format_time(time):

    if (not time):
        str_time = "LIVE"
    else:
        min = 60
        hr = 60
        day = 24

        formatted_min, formatted_sec = divmod(time, min)
        formatted_hr, formatted_min = divmod(formatted_min, hr)
        formatted_day, formatted_hr = divmod(formatted_hr, day)

        str_time = f"{formatted_min}:{formatted_sec}"

        if (formatted_day):
            str_time = f"{formatted_day}:{formatted_hr}:{str_time}"
        elif (formatted_hr):
            str_time = f"{formatted_hr}:{str_time}"

    return str_time

'''
format_filename(filename) Produces a new string from 'filename' with the
    characters that cannot be in a file's name replaced
format_filename: str -> str
'''
def format_filename(filename):
    filename = format_name(filename)
    chars_to_strip = {"\\" :"_", "/":"_", ":": "_" , "*":"#", "?":".", "<": "[", ">":"]", "|":"_", "\"":"'"}

    for c in chars_to_strip:
        filename = filename.replace(c, chars_to_strip[c])

    return filename


'''
format_date(date)  Produces a string from 'date' with slashes added to seperate
    the year, month and day
format_date: str -> str
'''
def format_date(date):
    return date[:4] + "/" + date[4:6] + "/" + date[6:]


'''
format_settings(key, value) Changes 'value' to be within the bounds of 'key'
format_settings: str, str -> str
'''
def format_settings(key, value):
    if (key == 'results/search' or key == 'results/page'):
        if (value.isnumeric()):
            if (int(value) < setup.limits["results/search"]["min"]):
                value = str(setup.limits["results/search"]["min"])
            elif (int(value) > setup.limits["results/search"]["max"]):
                value = str(setup.limits["results/search"]["max"])

        else:
            if (key == 'results/search'):
                value = str(setup.default["results/search"])
            else:
                value = str(setup.default['results/page'])

    return value


#copies the text onto the user's clipboard
def copy_text(text):
    pyperclip.copy(text)


#makes an image from a link
def process_image(link, img_w, img_h):
    response = requests.get(link)
    img_data = response.content
    photo = Image.open(BytesIO(img_data))

    return photo.resize((img_w, img_h),Image.ANTIALIAS)


#gets the image to be displayed
def load_image(resized_image, photo_lst, photo_num):
    photo_lst[photo_num] = ImageTk.PhotoImage(resized_image)
    return photo_lst
