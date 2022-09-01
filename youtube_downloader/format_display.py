import codecs, requests, re
from PIL import ImageTk, Image
from io import BytesIO
import pyperclip

import set_up


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
    return name


# add_leading_zero(str) Adds a leading zero to 'str'
def add_leading_zero(str: str, limit: int = 10) -> str:
    result = str

    try:
        int_str = int(str)

        if (int_str < limit):
            result = f"0{int_str}"
    except:
        pass

    return result


# format_time(time, verbose) Produces a string that divides 'time' into days, hours,
#    minutes and seconds
def format_time(time: int, verbose: bool = False) -> str:
    min = 60
    hr = 60
    day = 24

    formatted_min, formatted_sec = divmod(time, min)
    formatted_hr, formatted_min = divmod(formatted_min, hr)
    formatted_day, formatted_hr = divmod(formatted_hr, day)

    formatted_sec = add_leading_zero(formatted_sec)

    if (formatted_day or formatted_hr):
        formatted_min = add_leading_zero(formatted_min)

        if (formatted_day):
            formatted_hr = add_leading_zero(formatted_hr)

    if (not verbose):
        str_time = f"{formatted_min}:{formatted_sec}"

        if (formatted_day):
            str_time = f"{formatted_day}:{formatted_hr}:{str_time}"
        elif (formatted_hr):
            str_time = f"{formatted_hr}:{str_time}"
    else:
        str_time = f"{formatted_min} minute(s), {formatted_sec} second(s)"

        if (formatted_day):
            str_time = f"{formatted_day} day(s), {formatted_hr} hour(s), {str_time}"
        elif (formatted_hr):
            str_time = f"{formatted_hr} hour(s), {str_time}"

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
            if (int(value) < set_up.limits["results/search"]["min"]):
                value = str(set_up.limits["results/search"]["min"])
            elif (int(value) > set_up.limits["results/search"]["max"]):
                value = str(set_up.limits["results/search"]["max"])

        else:
            if (key == 'results/search'):
                value = str(set_up.default["results/search"])
            else:
                value = str(set_up.default['results/page'])

    return value


# remove_ansi_codes(txt): removes the ANSI escape sequences from 'txt'
def remove_ansi_codes(txt: str) -> str:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    result = ansi_escape.sub('', txt)
    return result


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
