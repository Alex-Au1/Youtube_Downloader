from youtubesearchpython import VideosSearch


'''
search_youtube_video(search_query) Produces a list of the video attributes
   based off the search, `search_query`
search_youtube_video: str -> List[List[Any[str, List[str]]]]
'''
def search_youtube_video(search_query, no_of_searches):
    results = []
    search = None
    results_len = len(results)
    start_search = False

    # retrieve all the searches needed
    while (results_len < no_of_searches):
        if (start_search):
            search.next()
        else:
            search = VideosSearch(search_query)
            start_search  = True

        search_results = search.result()["result"]

        if (search_results):
            results += search.result()["result"]
            results_len = len(results)
        else:
            break

    results = results[:no_of_searches]

    return results



'''
get_video_attributes(search, stack, attributes, result) Produces a list
   containing the different attributes of each video
get_video_attributes: List[str], List[str], List[Any[str, List[str]]] -> List[List[Any[str, List[str]]]]
'''
def get_video_attributes(search, stack, attributes, result):
    if (not search):
        return result

    #if the first element is the { open bracket
    elif(search[0] == "{"):
      if(not stack):
        stack.insert(0,"{")
        return get_video_attributes(search[1:], stack, attributes, result)

      else:
        inner_list = get_inner_list(search[1:], "{" ,[], [])
        attributes.append(inner_list[0])
        return get_video_attributes(inner_list[1], stack,attributes, result)

    #if the first element is the [ open bracket
    elif(search[0] == '"search_result": [' or search[0] == '"thumbnails": ['):
      if(not stack):
        stack.insert(0,"[")
        return get_video_attributes(search[1:], stack, attributes, result)

      else:
        inner_list = get_inner_list(search[1:], "[" ,[], [])
        attributes.append(inner_list[0])
        return get_video_attributes(inner_list[1], stack,attributes, result)

    #if the first element is the } closed bracket
    elif(search[0] == "}" or search[0] == "},"):
        if (stack[0] == "{"):
            stack.pop(0)
            result.append(attributes)
            attributes = []
            return get_video_attributes(search[1:], stack, attributes, result)
        else:
            print("Error: Invalid Brackets for {}")

    #if the first element is the } closed bracket
    elif(search[0] == "]" or search[0] == "],"):
        if(stack[0] == "["):
            stack.pop(0)
            result.append(attributes)
            attributes = []
            return get_video_attributes(search[1:], stack, attributes, result)
        else:
            print("Error: Invalid Brackets for []")

    #any other element that is not part of the {} or [] brackets
    else:
        attributes.append(get_only_attribute(search[0]))
        return get_video_attributes(search[1:], stack, attributes, result)


'''
get_inner_list(search, bracket, stack, result) Returns a list containing the
   elements of child array and the rest of the
   element in the parent array
get_inner_list: List[str], List[str], List[str], List[str] -> [List[str], List[str]]
'''
def get_inner_list(search, bracket ,stack, result):
  if(not search):
    print("0. Error: Invalid Brackets")

  # if the first element is the open bracket "{"
  elif(search[0] == "{"):
    stack.insert(0,"{")
    result.append(search[0])
    return get_inner_list(search[1:], bracket, stack, result)

  # if the first element is the open bracket "["
  elif(search[0] == '"search_result": [' or search[0] == '"thumbnails": ['):
    stack.insert(0,"[")
    result.append(search[0])
    return get_inner_list(search[1:], bracket, stack, result)

  #if the first element is the closed bracket "}"
  elif(search[0] == "}" or search[0] == "},"):
    #checks if the ending bracket corresponds with the to check open bracket
    if(not stack and bracket == "{"):
      result.insert(0, bracket)
      result.append("}")
      return [result, search[1:]]

    elif(stack):
      if(stack[0] == "{"):
        stack.pop(0)
        result.append("}")
        return get_inner_list(search[1:], bracket, stack, result)
      else:
        print("1. Error: Invalid Brackets {}")
    else:
      print("2. Error: Invalid Brackets {}")

  #if the first element is the closed bracket "]"
  elif(search[0] == "]" or search[0] == "],"):
    #checks if the ending bracket corresponds with the to check open bracket
    if(not stack and bracket == "["):
      return [result, search[1:]]

    elif(stack):
      if(stack[0] == "["):
        stack.pop(0)
        result.append("]")
        return get_inner_list(search[1:], bracket, stack, result)
      else:
        print("1. Error: Invalid Brackets []")
    else:
      print("2. Error: Invalid Brackets []")

  #appends any other character that is not a bracket to the result
  else:
    attribute = remove_comma(search[0])
    result.append(attribute[1:-1])
    return get_inner_list(search[1:], bracket, stack, result)



'''
get_only_attribute(attribute) Gets only the value of the attribute, removing all
   labels around the attribute
get_only_attribute: str -> str
'''
def get_only_attribute(attribute):
    attribute = remove_comma(attribute)

    colon = attribute.find(":")
    attribute = attribute[colon+1:].strip()

    if (attribute[0] == '"' and attribute[-1] == '"'):
        attribute = attribute[1:-1]

    return attribute


'''
remove_comma(attribute) Removes the comma at the end of an attribute
remove_comma: str -> str
'''
def remove_comma(attribute):
    if (attribute[-1] == ","):
        attribute = attribute[:-1]
    return attribute
