import csv
import json
import math
import os
import pandas as pd
import shutil
import struct
import sys

from audio import get_audio_samples_from_container
from utils import *

columns_to_keys = {
    0: "Key 1",
    1: "Key 2",
    2: "Key 3",
    3: "Key 4",
    4: "Key 5",
    5: "Key 6",
    6: "Key 7",
    7: "Scratch"
}

# initialize template bmson file
starter_bmson = {
    "version": "1.0.0",
    "info": {
        "init_bpm": 0,
        "resolution": 240
    },
    "lines": [],
    "bpm_events": [],
    "stop_events": [],
    "sound_channels": [],
    "bga": {}
}

EIGHT_ZERO_BYTES = b'\x00\x00\x00\x00\x00\x00\x00\x00'
END_OF_CHART = b'\xFF\xFF\xFF\x7F\x00\x00\x00\x00'


# For a specific offset in milliseconds and an array of bpm intervals, convert to pulses (where 1/4 note = 240 pulses)
def convert_to_pulses(ms: int, bpm_intervals: list):
    interval_index = len(bpm_intervals) - 1
    # find current interval
    # TODO: handle duplicate offsets
    if len(bpm_intervals) == 1:
        interval_index = 0
    else:
        while ms < bpm_intervals[interval_index][0]:
            interval_index -= 1

    return round((ms / (60 / bpm_intervals[interval_index][1])) * 240)


def parse_chart(song_id: int, chart_file, chart_offset: int, dir_index: int):
    data = pd.read_csv("data.csv", encoding="utf-8")
    data = data.to_dict('records')

    for entry in data:
        if entry["ID"] == int(f"{song_id:05d}"):
            print(f"Song entry {entry['ID']} found: \"{entry['ASCII TITLE']}\"")
            data = entry

    # Since data has been reassigned, if nothing changed the right entry is not found
    if len(data) > 16:
        sys.exit("Song entry must exist in data file but doesn't, exiting...")

    bmson = starter_bmson
    bmson["info"]["title"] = sanitize_input(data["TITLE"])
    bmson["info"]["subtitle"] = sanitize_input(data["SUBTITLE"])
    bmson["info"]["artist"] = sanitize_input(data["ARTIST"])
    bmson["info"]["genre"] = sanitize_input(data["GENRE"])
    bmson["info"]["mode_hint"] = "beat-7k" if dir_index > 6 else "beat-14k"

    if dir_index == 0:
        bmson["info"]["chart_name"] = "HYPER"
        bmson["info"]["level"] = int(data["SP-H"])
    elif dir_index == 1:
        bmson["info"]["chart_name"] = "NORMAL"
        bmson["info"]["level"] = int(data["SP-N"])
    elif dir_index == 2:
        bmson["info"]["chart_name"] = "ANOTHER"
        bmson["info"]["level"] = int(data["SP-A"])
    elif dir_index == 3:
        bmson["info"]["chart_name"] = "BEGINNER"
        bmson["info"]["level"] = int(data["SP-B"])
    elif dir_index == 4:
        bmson["info"]["chart_name"] = "LEGGENDARIA"
        bmson["info"]["level"] = int(data["SP-L"])
    elif dir_index == 6:
        bmson["info"]["chart_name"] = "HYPER"
        bmson["info"]["level"] = int(data["DP-H"])
    elif dir_index == 7:
        bmson["info"]["chart_name"] = "NORMAL"
        bmson["info"]["level"] = int(data["DP-N"])
    elif dir_index == 8:
        bmson["info"]["chart_name"] = "ANOTHER"
        bmson["info"]["level"] = int(data["DP-A"])
    elif dir_index == 10:
        bmson["info"]["chart_name"] = "LEGGENDARIA"
        bmson["info"]["level"] = int(data["DP-L"])

    audio_ext = bmson["info"]["preview_music"]
    audio_ext = audio_ext[len(audio_ext) - 3:]

    # initialize bpm and bpm intervals
    bpm_intervals = []

    chart_file.seek(chart_offset)
    event = chart_file.read(8)
    while event and END_OF_CHART not in event:
        event_offset = (event[3] << 24) | (event[2] << 16) | (event[1] << 8) | (event[0])
        event_type = event[4]
        event_param = event[5]
        event_value = (event[7] << 8) | (event[6])

        if event_type == 0x04:
            # handle event type 04 (bpm change)
            bpm = round(event_value / event_param)
            bpm_intervals.append([event_offset, bpm])
            print(f"Event at {event_offset}ms: BPM set to {(event_value // event_param)}")
            if bmson["info"]["init_bpm"] == 0:
                bmson["info"]["init_bpm"] = bpm
            else:
                bmson["bpm_events"].append({
                    "y": convert_to_pulses(event_offset, bpm_intervals),
                    "bpm": bpm
                })

        event = chart_file.read(8)

    print("End of chart reached.")

    # ready to parse chart
    chart_file.seek(chart_offset)
    event = chart_file.read(8)
    while event and END_OF_CHART not in event:
        event_offset = (event[3] << 24) | (event[2] << 16) | (event[1] << 8) | (event[0])
        event_type = event[4]
        event_param = event[5]
        event_value = (event[7] << 8) | (event[6])

        if event_type == 0x00:
            # handle event type 00 (visible note on playfield for P1)
            print(
                f"Event at {event_offset}ms: Visible note for P1: {columns_to_keys[event_param]}{', hold for ' + str(event_value) + 'ms' if event_value > 0 else ''}")
        elif event_type == 0x01:
            # handle event type 01 (visible note on playfield for P2)
            print(
                f"Event at {event_offset}ms: Visible note for P2: {columns_to_keys[event_param]}{', hold for ' + str(event_value) + 'ms' if event_value > 0 else ''}")
        elif event_type == 0x02:
            # handle event type 02 (sample change for P1)
            print(
                f"Event at {event_offset}ms: Sample change for P1: {columns_to_keys[event_param]} => sample {event_value}")
        elif event_type == 0x03:
            # handle event type 03 (sample change for P2)
            print(
                f"Event at {event_offset}ms: Sample change for P2: {columns_to_keys[event_param]} => sample {event_value}")
        elif event_type == 0x04:
            # we already did this, so ignore
            print(f"Event at {event_offset}ms: BPM change, ignoring.")
        elif event_type == 0x05:
            # handle (or more specifically, don't handle) event type 05 (meter info)
            print(f"Event at {event_offset}ms: Meter information, ignoring.")
        elif event_type == 0x06:
            # handle event type 06 (end of song)
            print(f"Event at {event_offset}ms: End of song, ignoring.")
            break
        elif event_type == 0x07:
            # handle event type 07 (background sample)
            print(f"Event at {event_offset}ms: Background sample {event_value}")
        elif event_type == 0x08:
            # handle (or more specifically, don't handle) event type 08 (timing window info)
            print(f"Event at {event_offset}ms: Timing window information, ignoring.")
        elif event_type == 0x0C:
            # handle event type 0C (measure bar)
            print(f"Event at {event_offset}ms: Measure bar for P{event_param + 1}")
            # bmson["lines"].append({"k": 0, "y": convert_to_pulses(file_offset, bpm_intervals)})
        elif event_type == 0x10:
            # handle event type 10 (note count)
            print(f"Event at {event_offset}ms: Note count for P{event_param + 1}: {event_value}")
        else:
            # handle unknown events
            sys.exit(
                f"Unknown event at {event_offset}ms, type {hex(event_type)}, param {hex(event_param)} and value {hex(event_value)}. Time to debug and figure it out!")

        event = chart_file.read(8)

    print("End of chart reached.")


def parse_all_charts_and_audio(contents_dir, song_id: int, convert_to_ogg=True):
    # create output directory if it doesn't exist yet
    output_path = f"{os.path.join('.', 'out', str(song_id))}"
    if os.path.exists(output_path):
        print(f"Output path {output_path} already exists, using it.")
    else:
        os.makedirs(output_path)
        print(f"Output path {output_path} created.")

    # check if title image path exists, and if so import it (optional)
    title_image_path = os.path.join(contents_dir, "data", "graphic", f"i_{song_id}_ifs", f"i_{song_id}.png")
    if os.path.exists(title_image_path):
        print(f"Found title image file {os.path.basename(title_image_path)}, importing it...")
        shutil.copy(title_image_path, output_path)
        title_image_path = os.path.join("out", str(song_id), os.path.basename(title_image_path))
        starter_bmson["title_image"] = title_image_path
    else:
        print("No title image found, I hope you know what you're doing!")

    # check if eyecatch image path exists, and if so import it (optional)
    eyecatch_image_path = os.path.join("custom", "eyecatches", f"{song_id}.jpg")
    if os.path.exists(eyecatch_image_path):
        print(f"Found eyecatch image file {os.path.basename(eyecatch_image_path)}, importing it...")
        shutil.copy(eyecatch_image_path, output_path)
        eyecatch_image_path = os.path.join("out", str(song_id), os.path.basename(eyecatch_image_path))
        starter_bmson["eyecatch_image"] = eyecatch_image_path
    else:
        print("No eyecatch image found, I hope you know what you're doing!")

    # check if video path exists, and if so import it (optional)
    video_path = ""
    if os.path.exists(os.path.join("custom", "videos", f"{song_id}.mp4")):
        video_path = os.path.join("custom", "videos", f"{song_id}.mp4")
    elif os.path.exists(os.path.join(contents_dir, "data", "movie", f"{song_id}.mp4")):
        video_path = os.path.join(contents_dir, "data", "movie", f"{song_id}.mp4")
    else:
        print("No video found, I hope you know what you're doing!")

    if video_path != "":
        print(f"Found video file {os.path.basename(video_path)}, importing it...")
        shutil.copy(video_path, output_path)
        video_path = os.path.join("out", str(song_id), os.path.basename(video_path))
        # noinspection PyTypeChecker
        starter_bmson["bga"]["bga_header"] = ["bga", video_path]

    # check if chart file path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.1")):
        chart_path = os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.1")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.1")):
        chart_path = os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.1")
    else:
        sys.exit("Invalid chart path, exiting...")

    print(f"Found chart file {os.path.basename(chart_path)}, importing it...")
    shutil.copy(chart_path, output_path)
    chart_path = os.path.join("out", str(song_id), os.path.basename(chart_path))

    # check if song container path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.2dx")):
        container_path = os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.2dx")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.s3p")):
        container_path = os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.s3p")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.2dx")):
        container_path = os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.2dx")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.s3p")):
        container_path = os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.s3p")
    else:
        sys.exit("Invalid container path, exiting...")

    print(f"Found container file {os.path.basename(container_path)}, importing it...")
    shutil.copy(container_path, output_path)
    container_path = os.path.join("out", str(song_id), os.path.basename(container_path))

    # check if song preview path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}_pre.2dx")):
        preview_path = os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}_pre.2dx")
    elif os.path.exists(
            os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}_pre.2dx")):
        preview_path = os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}_pre.2dx")
    else:
        sys.exit("Invalid preview path, exiting...")

    print(f"Found preview file {os.path.basename(preview_path)}, importing it...")
    shutil.copy(preview_path, output_path)
    preview_path = os.path.join("out", str(song_id), os.path.basename(preview_path))

    # extract audio preview
    extracted_preview_path = \
        get_audio_samples_from_container(song_id,
                                         os.path.join(".", "out", str(song_id), os.path.basename(preview_path)))[0]
    starter_bmson["info"]["preview_music"] = os.path.join(os.path.basename(container_path).split(".")[0],
                                                          os.path.basename(extracted_preview_path))

    # TODO: implement sound_channels
    # sound_channels = get_audio_samples_from_container(str(song_id), os.path.join(".", "out", os.path.basename(container_path)))

    # parse chart directory entries
    with open(chart_path, 'rb') as chart_file:
        chart_directory = []
        file_offset = 0
        for i in range(12):
            chart_file.seek(file_offset)
            chart_directory.append(struct.unpack("<I", chart_file.read(4))[0])
            file_offset += 8

        # iterate over all charts found inside chart file
        # but for now, we start with the SP-NORMAL chart
        for i in range(len(chart_directory)):
            if chart_directory[i] != 0:
                parse_chart(song_id, chart_file, chart_directory[i], i)