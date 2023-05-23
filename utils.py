import os
import sys
from termcolor import cprint


def success(text):
    cprint(text, "green")


def warning(text):
    cprint("(?) " + text, "yellow")


def error(text):
    cprint("[!] " + text, "red")
    sys.exit()


def sanitize_input(data):
    if data != data:  # this checks for misc. NaNs
        data = ""

    data = data.replace('\xa0', ' ')
    return data


# For a specific offset in milliseconds and an array of bpm intervals, convert to pulses (where 1/4 note = 240 pulses)
def convert_to_pulses(offset_ms, tempo_changes, pulses_per_beat=240):
    current_bpm = tempo_changes[0][1]
    current_time = 0
    pulses = 0
    for i in range(len(tempo_changes)):
        if offset_ms < tempo_changes[i][0]:
            break
        ms_per_pulse = (60 * 1000) / (current_bpm * pulses_per_beat)
        pulses += (tempo_changes[i][0] - current_time) / ms_per_pulse
        current_time = tempo_changes[i][0]
        current_bpm = tempo_changes[i][1]
    else:
        i += 1
    ms_per_pulse = (60 * 1000) / (current_bpm * pulses_per_beat)
    pulses += (offset_ms - current_time) / ms_per_pulse
    return int(pulses)


def handle_container_edge_case(container_dir, song_id, dir_index):
    return container_dir.split(os.path.sep).append()
