def sanitize_input(data):
    if data != data:  # this checks for misc. NaNs
        data = ""
    
    data = data.replace(u'\xa0', u' ')
    return data
