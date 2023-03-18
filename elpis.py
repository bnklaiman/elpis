import json
import os
import pandas as pd
import shutil
import struct
import sys
from typing import List

from audio import get_audio_samples_from_container, generate_bgm
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
        "title": "",
        "subtitle": "",
        "artist": "",
        "subartists": [],
        "genre": [],
        "mode_hint": "",
        "chart_name": "",
        "level": 0,
        "init_bpm": 0,
        "judge_rank": 100,
        "total": 100,
        "back_image": "",
        "eyecatch_image": "",
        "banner_image": "",
        "preview_music": "",
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


def parse_chart(song_id, chart_file, chart_offset, dir_index, audio_samples):
    data = pd.read_csv("data.csv", encoding="utf-8")
    data = data.to_dict('records')

    for entry in data:
        if entry["ID"] == int(f"{song_id:05d}"):
            print(
                f"Song entry {entry['ID']} found: \"{entry['ASCII TITLE']}\"")
            data = entry

    # Since data has been reassigned, if nothing changed the right entry is not found
    if len(data) > 16:
        sys.exit("Song entry must exist in data file but doesn't, exiting...")

    bmson = starter_bmson
    bmson["info"]["title"] = sanitize_input(data["TITLE"])
    bmson["info"]["subtitle"] = sanitize_input(data["SUBTITLE"])
    bmson["info"]["artist"] = sanitize_input(data["ARTIST"])
    bmson["info"]["genre"] = sanitize_input(data["GENRE"])
    bmson["info"]["mode_hint"] = "beat-7k" if dir_index < 6 else "beat-14k"

    bmson_output_filename = f"{song_id}-"

    if dir_index == 0:
        bmson["info"]["chart_name"] = "SP HYPER"
        bmson["info"]["level"] = int(data["SP-H"])
        bmson_output_filename += "SP-H.bmson"
    elif dir_index == 1:
        bmson["info"]["chart_name"] = "SP NORMAL"
        bmson["info"]["level"] = int(data["SP-N"])
        bmson_output_filename += "SP-N.bmson"
    elif dir_index == 2:
        bmson["info"]["chart_name"] = "SP ANOTHER"
        bmson["info"]["level"] = int(data["SP-A"])
        bmson_output_filename += "SP-A.bmson"
    elif dir_index == 3:
        bmson["info"]["chart_name"] = "SP BEGINNER"
        bmson["info"]["level"] = int(data["SP-B"])
        bmson_output_filename += "SP-B.bmson"
    elif dir_index == 4:
        bmson["info"]["chart_name"] = "SP LEGGENDARIA"
        bmson["info"]["level"] = int(data["SP-L"])
        bmson_output_filename += "SP-L.bmson"
    elif dir_index == 6:
        bmson["info"]["chart_name"] = "DP HYPER"
        bmson["info"]["level"] = int(data["DP-H"])
        bmson_output_filename += "DP-H.bmson"
    elif dir_index == 7:
        bmson["info"]["chart_name"] = "DP NORMAL"
        bmson["info"]["level"] = int(data["DP-N"])
        bmson_output_filename += "DP-N.bmson"
    elif dir_index == 8:
        bmson["info"]["chart_name"] = "DP ANOTHER"
        bmson["info"]["level"] = int(data["DP-A"])
        bmson_output_filename += "DP-A.bmson"
    elif dir_index == 10:
        bmson["info"]["chart_name"] = "DP LEGGENDARIA"
        bmson["info"]["level"] = int(data["DP-L"])
        bmson_output_filename += "DP-L.bmson"

    # initialize sound_channels JSON object
    sound_channels = []
    for i in range(len(audio_samples)):
        sound_channels.append({"name": audio_samples[i], "notes": []})

    current_samples = [[0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]]

    # initialize bpm and bpm intervals, and background audio samples and their respective offsets
    bpm_intervals = []
    chart_file.seek(chart_offset)
    event = chart_file.read(8)
    bgm_samples = []
    bgm_exists = False
    while event and END_OF_CHART not in event:
        event_offset = (event[3] << 24) | (
            event[2] << 16) | (event[1] << 8) | (event[0])
        event_type = event[4]
        event_param = event[5]
        event_value = (event[7] << 8) | (event[6])

        if event_type == 0x04:
            # handle event type 04 (bpm change)
            bpm = round(event_value / event_param)
            bpm_intervals.append([event_offset, bpm])

            if bmson["info"]["init_bpm"] == 0:
                bmson["info"]["init_bpm"] = bpm
                print(
                    f"Event at {event_offset}ms: BPM initialized to {round(event_value / event_param)}")
            else:
                for interval in bpm_intervals:
                    if interval[0] == event_offset:
                        print(
                            f"BPM change event already exists at {event_offset}ms, ignoring.")
                    else:
                        bmson["bpm_events"].append({
                            "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                            "bpm": bpm
                        })
                        print(
                            f"Event at {event_offset}ms: BPM change to {round(event_value / event_param)}")
        elif event_type == 0x07:
            # handle event type 07 (background sample)
            print(
                f"Event at {event_offset}ms: Background sample {event_value - 1} (0-indexed)")
            bgm_samples.append([event_offset, event_value - 1])
            # TODO: change this
            if bgm_exists == False:
                bgm_exists = True

        event = chart_file.read(8)

    # replace indices in bgm_samples with the actual files
    for i in range(len(bgm_samples)):
        index = bgm_samples[i][1]
        bgm_samples[i][1] = sound_channels[index]["name"]

    # generate bgm track for this specific chart
    bgm_name = generate_bgm(bgm_samples, song_id, dir_index)

    note = {
        "x": 0,
        "y": 0,
        "l": 0,
        "c": False
    }
    sound_channels.append({"name": bgm_name, "notes": [note]})
    print("End of chart reached.")

    # ready to parse chart
    chart_file.seek(chart_offset)
    event = chart_file.read(8)
    while event and END_OF_CHART not in event:
        event_offset = (event[3] << 24) | (
            event[2] << 16) | (event[1] << 8) | (event[0])
        event_type = event[4]
        event_param = event[5]
        event_value = (event[7] << 8) | (event[6])

        if event_type == 0x00:
            # handle event type 00 (visible note on playfield for P1)
            print(
                f"Event at {event_offset}ms: Visible note for P1: ",
                f"{columns_to_keys[event_param]}{', hold for ' + str(event_value) + 'ms' if event_value > 0 else ''}")
            note = {
                "x": event_param + 1,
                "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                "l": convert_to_pulses(event_value, bpm_intervals, starter_bmson["info"]["resolution"]),
                "c": False
            }
            sound_channels[current_samples[0]
                           [event_param]]["notes"].append(note)
        elif event_type == 0x01:
            # handle event type 01 (visible note on playfield for P2)
            print(
                f"Event at {event_offset}ms: Visible note for P2: ",
                f"{columns_to_keys[event_param]}{', hold for ' + str(event_value) + 'ms' if event_value > 0 else ''}")
            note = {
                "x": event_param + 9,
                "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                "l": convert_to_pulses(event_value, bpm_intervals, starter_bmson["info"]["resolution"]),
                "c": False
            }
            sound_channels[current_samples[1]
                           [event_param]]["notes"].append(note)
        elif event_type == 0x02:
            # handle event type 02 (sample change for P1)
            print(
                f"Event at {event_offset}ms: Sample change for P1: ",
                f"{columns_to_keys[event_param]} => sample {event_value - 1} (0-indexed)")
            current_samples[0][event_param] = event_value - 1
        elif event_type == 0x03:
            # handle event type 03 (sample change for P2)
            print(
                f"Event at {event_offset}ms: Sample change for P2: ",
                f"{columns_to_keys[event_param]} => sample {event_value - 1} (0-indexed)")
            current_samples[1][event_param] = event_value - 1
        elif event_type == 0x04:
            # we already did this, so ignore
            print(f"Event at {event_offset}ms: BPM change, ignoring.")
        elif event_type == 0x05:
            # handle (or more specifically, don't handle) event type 05 (meter info)
            print(f"Event at {event_offset}ms: Meter information, ignoring.")
        elif event_type == 0x06:
            # handle event type 06 (end of song)
            print(f"Event at {event_offset}ms: End of song, ignoring.")
        elif event_type == 0x07:
            # we already did this, so ignore.
            print(
                f"Event at {event_offset}ms: Background sample, ignoring.")
        elif event_type == 0x08:
            # handle (or more specifically, don't handle) event type 08 (timing window info)
            print(
                f"Event at {event_offset}ms: Timing window information, ignoring.")
        elif event_type == 0x0C:
            # handle event type 0C (measure bar)
            print(
                f"Event at {event_offset}ms: Measure bar for P{event_param + 1}")
            bmson["lines"].append({"y": convert_to_pulses(
                event_offset, bpm_intervals, starter_bmson["info"]["resolution"])})
        elif event_type == 0x10:
            # handle event type 10 (note count)
            print(
                f"Event at {event_offset}ms: Note count for P{event_param + 1}: {event_value}")
        else:
            # handle unknown events
            sys.exit(
                f"Unknown event at {event_offset}ms, type {hex(event_type)}, param {hex(event_param)} and value {hex(event_value)}.")

        event = chart_file.read(8)

    print("End of chart reached.")
    bmson["sound_channels"] = sound_channels
    bmson_output_filename = os.path.join(
        "out", str(song_id), bmson_output_filename)
    print(f"Writing to file \'{os.path.basename(bmson_output_filename)}\'...")
    with open(bmson_output_filename, "w", encoding="utf-8") as file:
        json.dump(bmson, file, ensure_ascii=False, sort_keys=True)

    print(f"\'{os.path.basename(bmson_output_filename)}\' written.")


def parse_all_charts_and_audio(contents_dir, song_id):
    # create output directory if it doesn't exist yet
    output_path = f"{os.path.join('.', 'out', str(song_id))}"
    if os.path.exists(output_path):
        print(f"Output path {output_path} already exists, using it.")
    else:
        os.makedirs(output_path)
        print(f"Output path {output_path} created.")

    # check if title image path exists, and if so import it (optional)
    title_image_path = os.path.join(
        contents_dir, "data", "graphic", f"i_{song_id}_ifs", f"i_{song_id}.png")
    if os.path.exists(title_image_path):
        print(
            f"Found title image file {os.path.basename(title_image_path)}, importing it...")
        shutil.copy(title_image_path, output_path)
        title_image_path = os.path.join("out", str(
            song_id), os.path.basename(title_image_path))
        starter_bmson["info"]["title_image"] = os.path.basename(
            title_image_path)
    else:
        print("No title image found, I hope you know what you're doing!")

    # check if eyecatch image path exists, and if so import it (optional)
    eyecatch_image_path = os.path.join(
        "custom", "eyecatches", f"{song_id}.jpg")
    if os.path.exists(eyecatch_image_path):
        print(
            f"Found eyecatch image file {os.path.basename(eyecatch_image_path)}, importing it...")
        shutil.copy(eyecatch_image_path, output_path)
        eyecatch_image_path = os.path.join("out", str(
            song_id), os.path.basename(eyecatch_image_path))
        starter_bmson["info"]["eyecatch_image"] = os.path.basename(
            eyecatch_image_path)
    else:
        print("No eyecatch image found, I hope you know what you're doing!")

    # check if video path exists, and if so import it (optional)
    video_path = ""
    if os.path.exists(os.path.join("custom", "videos", f"{song_id}.mp4")):
        video_path = os.path.join("custom", "videos", f"{song_id}.mp4")
    elif os.path.exists(os.path.join(contents_dir, "data", "movie", f"{song_id}.mp4")):
        video_path = os.path.join(
            contents_dir, "data", "movie", f"{song_id}.mp4")
    else:
        print("No video found, I hope you know what you're doing!")

    if video_path != "":
        print(
            f"Found video file {os.path.basename(video_path)}, importing it...")
        shutil.copy(video_path, output_path)
        video_path = os.path.join("out", str(
            song_id), os.path.basename(video_path))
        # starter_bmson["bga"]["bga_header"] = ["bga", video_path]

    # check if chart file path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.1")):
        chart_path = os.path.join(
            contents_dir, "data", "sound", str(song_id), f"{song_id}.1")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.1")):
        chart_path = os.path.join(
            contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.1")
    else:
        sys.exit("Invalid chart path, exiting...")

    print(f"Found chart file {os.path.basename(chart_path)}, importing it...")
    shutil.copy(chart_path, output_path)
    chart_path = os.path.join("out", str(
        song_id), os.path.basename(chart_path))

    # check if song container path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.2dx")):
        container_path = os.path.join(
            contents_dir, "data", "sound", str(song_id), f"{song_id}.2dx")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}.s3p")):
        container_path = os.path.join(
            contents_dir, "data", "sound", str(song_id), f"{song_id}.s3p")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.2dx")):
        container_path = os.path.join(
            contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.2dx")
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.s3p")):
        container_path = os.path.join(
            contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}.s3p")
    else:
        sys.exit("Invalid container path, exiting...")

    print(
        f"Found container file {os.path.basename(container_path)}, importing it...")
    shutil.copy(container_path, output_path)
    container_path = os.path.join("out", str(
        song_id), os.path.basename(container_path))

    # check if song preview path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id), f"{song_id}_pre.2dx")):
        preview_path = os.path.join(
            contents_dir, "data", "sound", str(song_id), f"{song_id}_pre.2dx")
    elif os.path.exists(
            os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id), f"{song_id}_pre.2dx")):
        preview_path = os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(
            song_id), f"{song_id}_pre.2dx")
    else:
        sys.exit("Invalid preview path, exiting...")

    print(
        f"Found preview file {os.path.basename(preview_path)}, importing it...")
    shutil.copy(preview_path, output_path)
    preview_path = os.path.join("out", str(
        song_id), os.path.basename(preview_path))

    # extract audio preview
    extracted_preview_path = \
        get_audio_samples_from_container(song_id,
                                         os.path.join(".", "out", str(song_id), os.path.basename(preview_path)))[0]
    starter_bmson["info"]["preview_music"] = os.path.join(os.path.basename(container_path).split(".")[0],
                                                          os.path.basename(extracted_preview_path))

    audio_samples = get_audio_samples_from_container(song_id, container_path)

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
                parse_chart(song_id, chart_file,
                            chart_directory[i], i, audio_samples)

    # we're done with source files, remove them from output directory
    os.remove(chart_path)
    print(f"{os.path.basename(chart_path)} removed.")
    os.remove(container_path)
    print(f"{os.path.basename(preview_path)} removed.")
    os.remove(preview_path)
    print(f"{os.path.basename(preview_path)} removed.")
