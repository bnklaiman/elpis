def sanitize_input(data):
    if data != data:  # this checks for misc. NaNs
        data = ""
    
    data = data.replace(u'\xa0', u' ')
    return data


# For a specific offset in milliseconds and an array of bpm intervals, convert to pulses (where 1/4 note = 240 pulses)
def convert_to_pulses(ms, bpm_intervals, resolution=240):
    interval_index = len(bpm_intervals) - 1
    # find current interval
    if len(bpm_intervals) == 1:
        interval_index = 0
    else:
        while ms < bpm_intervals[interval_index][0]:
            interval_index -= 1

    return round((ms * resolution) / (60000 / bpm_intervals[interval_index][1]))