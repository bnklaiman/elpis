import json
import os
import re
import shutil
import struct

from audio import get_audio_samples_from_container, generate_bgm
from utils import *
from Misc_enums import *

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

alt_containers = json.load(open('ALT_CONTAINER_FILE'))

EIGHT_ZERO_BYTES = b'\x00\x00\x00\x00\x00\x00\x00\x00'
END_OF_CHART = b'\xFF\xFF\xFF\x7F\x00\x00\x00\x00'


def cleanup_bmson(bmson):
    nonempty_sound_channels = []
    for sound_channel in bmson["sound_channels"]:
        if sound_channel["notes"] != []:
            nonempty_sound_channels.append(sound_channel)
    bmson["sound_channels"] = nonempty_sound_channels
    return bmson


def parse_chart(contents_dir, song_id, db_entry, chart_file, chart_offset, dir_index, container_path):
    # handle audio container edge cases: check if the container directory exists instead of the container itself
    if container_path == "":
        container_dir = ""
        if os.path.exists(os.path.join(contents_dir, "data", "sound", str(song_id))):
            container_dir = os.path.join(
                contents_dir, "data", "sound", str(song_id))
        elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id))):
            container_dir = os.path.join(
                contents_dir, "data", "sound", f"{song_id}_ifs", str(song_id))
        else:
            error("Invalid container directory edge case, exiting...")

        # Since there are multiple audio containers, import all of them
        output_path = f"{os.path.join('.', 'out', str(song_id))}"
        print("Looking for audio container files...")
        for root, _, filenames in os.walk(container_dir):
            for file in filenames:
                (_, extension) = os.path.splitext(file)
                if extension == ".2dx" or extension == ".s3p":
                    shutil.copy(os.path.join(root, file), os.path.join(
                        output_path, os.path.relpath(os.path.join(root, file), container_dir)))
        
    
    if song_id in alt_containers:
        if chart_names[str(dir_index)] in alt_containers[song_id]:
            container_path = os.path.join(".", "out", song_id, alt_containers[song_id][chart_names[str(dir_index)]])
    else:
        print("No alternate containers found.")

    try:
        audio_samples = get_audio_samples_from_container(song_id, container_path, db_entry["volume"] / 100)
    except ValueError:
        error("ValueError: This song should use an alternate audio container, but isn't.")

    bmson = starter_bmson
    bmson["info"]["title"] = db_entry["title"]
    bmson["info"]["artist"] = db_entry["artist"]
    bmson["info"]["genre"] = db_entry["genre"]
    bmson["info"]["mode_hint"] = "beat-7k" if dir_index < 6 else "beat-14k"

    match dir_index:
        case 0:
            bmson["info"]["level"] = db_entry["SPH_level"]
            bmson["info"]["chart_name"] = "HYPER"
        case 1:
            bmson["info"]["level"] = db_entry["SPN_level"]
            bmson["info"]["chart_name"] = "NORMAL"
        case 2:
            bmson["info"]["level"] = db_entry["SPA_level"]
            bmson["info"]["chart_name"] = "ANOTHER"
        case 3:
            bmson["info"]["level"] = db_entry["SPB_level"]
            bmson["info"]["chart_name"] = "BEGINNER"
        case 4:
            bmson["info"]["level"] = db_entry["SPL_level"]
            bmson["info"]["chart_name"] = "LEGGENDARIA"
        case 6:
            bmson["info"]["level"] = db_entry["DPH_level"]
            bmson["info"]["chart_name"] = "HYPER"
        case 7:
            bmson["info"]["level"] = db_entry["DPN_level"]
            bmson["info"]["chart_name"] = "NORMAL"
        case 8:
            bmson["info"]["level"] = db_entry["DPA_level"]
            bmson["info"]["chart_name"] = "ANOTHER"
        case 9:
            bmson["info"]["level"] = db_entry["DPB_level"]
            bmson["info"]["chart_name"] = "BEGINNER"
        case 10:
            bmson["info"]["level"] = db_entry["DPL_level"]
            bmson["info"]["chart_name"] = "LEGGENDARIA"

    bmson_output_filename = f"{song_id}-{chart_names[str(dir_index)]}.bmson"

    # initialize sound_channels JSON object
    sound_channels = []
    for i in range(len(audio_samples)):
        sound_channels.append({"name": audio_samples[i], "notes": []})

    current_samples = {
        "P1": [0, 0, 0, 0, 0, 0, 0, 0],
        "P2": [0, 0, 0, 0, 0, 0, 0, 0],
    }

    # initialize bpm and bpm intervals, and background audio samples and their respective offsets
    bpm_intervals = []
    chart_file.seek(chart_offset)
    event = chart_file.read(8)
    bgm_samples = []
    bmson["bpm_events"] = []
    bmson["lines"] = []
    while event and END_OF_CHART not in event:
        event_offset = (event[3] << 24) | (
            event[2] << 16) | (event[1] << 8) | (event[0])
        event_type = event[4]
        event_param = event[5]
        event_value = (event[7] << 8) | (event[6])

        match event_type:
            case 0x04:
                # handle event type 04 (bpm change)
                try:
                    bpm = round(event_value / event_param)
                except ZeroDivisionError:
                    # prevent division by zero, thereby averting the implosion of the space-time continuum
                    bpm = round(event_value)
                bpm_intervals.append([event_offset, bpm])

                if bmson["info"]["init_bpm"] == 0:
                    bmson["info"]["init_bpm"] = bpm
                    bmson["bpm_events"].append({
                        "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                        "bpm": bpm
                    })
                    print(
                        f"Event at {event_offset}ms: BPM initialized to {bpm}")
                else:
                    if bpm_intervals[-1] == event_offset:
                        print(
                            f"BPM change event already exists at {event_offset}ms, ignoring.")
                    else:
                        bmson["bpm_events"].append({
                            "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                            "bpm": bpm
                        })
                        print(
                            f"Event at {event_offset}ms: BPM change to {bpm}")
            case 0x07:
                # handle event type 07 (background sample)
                print(
                    f"Event at {event_offset}ms: Background sample {event_value - 1} (0-indexed)")
                bgm_samples.append([event_offset, event_value - 1])

        event = chart_file.read(8)

    # replace indices in bgm_samples with the actual files
    for i in range(len(bgm_samples)):
        index = bgm_samples[i][1]
        try:
            bgm_samples[i][1] = sound_channels[index]["name"]
        except IndexError:
            error(f"IndexError: Sample index out of range for this container! This is probably the wrong container for the {chart_names[str(dir_index)]} chart.")

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

        is_event_mss = event_param == 0x6B
        match event_type:
            case 0x00:
                # handle event type 00 (visible note on playfield for P1)
                if is_event_mss:
                    # handle Multi-Spin Scratch
                    event_param = 0x07
                    print(
                        f"Event at {event_offset}ms: Multi-Spin Scratch for P1,",
                        f"hold for {event_value}ms")
                else:
                    print(
                        f"Event at {event_offset}ms: Visible note for P1:",
                        f"{columns_to_keys[event_param]}{', hold for ' + str(event_value) + 'ms' if event_value > 0 else ''}")
                note = {
                    "x": event_param + 1,
                    "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                    "l": convert_to_pulses(event_value,  bpm_intervals, starter_bmson["info"]["resolution"]),
                    "c": False
                }
                # give some space between MSS to prevent timing window overlap
                if is_event_mss: 
                    note["l"] -= 3
                
                if current_samples["P1"][event_param] <= len(sound_channels):
                    sound_channels[current_samples["P1"][event_param]]["notes"].append(note)
                else:
                    error(f"IndexError: Audio container not found! This is the wrong container for the {chart_names[str(dir_index)]} chart.")
            case 0x01:
                # handle event type 01 (visible note on playfield for P2)
                if is_event_mss:
                    # handle Multi-Spin Scratch
                    event_param = 0x07
                    print(
                        f"Event at {event_offset}ms: Multi-Spin Scratch for P2,",
                        f"hold for {event_value}ms")
                else:
                    print(
                        f"Event at {event_offset}ms: Visible note for P2:",
                        f"{columns_to_keys[event_param]}{', hold for ' + str(event_value) + 'ms' if event_value > 0 else ''}")
                note = {
                    "x": event_param + 9,
                    "y": convert_to_pulses(event_offset, bpm_intervals, starter_bmson["info"]["resolution"]),
                    "l": convert_to_pulses(event_value,  bpm_intervals, starter_bmson["info"]["resolution"]),
                    "c": False
                }
                # give some space between MSS to prevent timing window overlap
                if is_event_mss:
                    note["l"] -= 3
                
                if current_samples["P2"][event_param] <= len(sound_channels):
                    sound_channels[current_samples["P2"][event_param]]["notes"].append(note)
                else:
                    error(f"IndexError: Audio container not found! This is the wrong container for the {chart_names[str(dir_index)]} chart.")
            case 0x02:
                # handle event type 02 (sample change for P1)
                if event_param != 8:
                    # malformed event, discovered in song id #01002
                    print(
                        f"Event at {event_offset}ms: Sample change for P1:",
                        f"{columns_to_keys[event_param]} => sample {event_value - 1} (0-indexed)")
                    current_samples["P1"][event_param] = event_value - 1
                else:
                    print(f"Event at {event_offset}ms: ILLEGAL SAMPLE CHANGE for P1: Key {event_param} does not exist!")
            case 0x03:
                # handle event type 03 (sample change for P2)
                if event_param != 8:
                    # malformed event, discovered in song id #01002
                    print(
                        f"Event at {event_offset}ms: Sample change for P2:",
                        f"{columns_to_keys[event_param]} => sample {event_value - 1} (0-indexed)")
                    current_samples["P2"][event_param] = event_value - 1
                else:
                    print(f"Event at {event_offset}ms: ILLEGAL SAMPLE CHANGE for P2: Key {event_param} does not exist!")
            case 0x04:
                # we already did this, so ignore
                print(
                    f"Event at {event_offset}ms: BPM change, ignoring.")
            case 0x05:
                # handle (or more specifically, don't handle) event type 05 (meter info)
                print(
                    f"Event at {event_offset}ms: Meter information, ignoring.")
            case 0x06:
                # handle event type 06 (end of song)
                print(
                    f"Event at {event_offset}ms: End of song, ignoring.")
            case 0x07:
                # we already did this, so ignore.
                print(
                    f"Event at {event_offset}ms: Background sample, ignoring.")
            case 0x08:
                # handle (or more specifically, don't handle) event type 08 (timing window info)
                print(
                    f"Event at {event_offset}ms: Timing window information, ignoring.")
            case 0x0C:
                # handle event type 0C (measure bar)
                print(
                    f"Event at {event_offset}ms: Measure bar for P{event_param + 1}")
                bmson["lines"].append({"y": convert_to_pulses(
                    event_offset, bpm_intervals, starter_bmson["info"]["resolution"])})
            case 0x10:
                # handle event type 10 (note count)
                print(
                    f"Event at {event_offset}ms: Note count for P{event_param + 1}: {event_value}")
            case _:
                # handle unknown event types
                if event_type not in unknown_events:
                    error(
                        f"Unknown event at {event_offset}ms, type {hex(event_type)}, param {hex(event_param)} and value {hex(event_value)}.")

        event = chart_file.read(8)

    # Update video delay
    video_delay = db_entry["bga_delay"]
    if video_delay < 0:
        video_delay = 0
    bmson["bga"]["bga_events"] = [{"id": 1, "y": convert_to_pulses(video_delay, bpm_intervals, starter_bmson["info"]["resolution"]) * 20}]


    print("End of chart reached.")
    bmson["sound_channels"] = sound_channels
    bmson = cleanup_bmson(bmson)
    bmson_output_filename = os.path.join(
        "out", str(song_id), bmson_output_filename)
    with open(bmson_output_filename, "w", encoding="utf-8") as file:
        json.dump(bmson, file, ensure_ascii=False, sort_keys=True)

    success(f"{os.path.basename(bmson_output_filename)} written.")


def parse_all_charts_and_audio(contents_dir, song_id, db_entry):
    # create output directory if it doesn't exist yet
    output_path = f"{os.path.join('.', 'out', str(song_id))}"
    if os.path.exists(output_path):
        print(f"Output path {output_path} already exists, using it.")
    else:
        os.makedirs(output_path)
        print(f"Output path {output_path} created.")

    # External files

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
        print("No title image found, this is probably intentional.")

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
        warning("No eyecatch image found, I hope you know what you're doing!")

    # check if video path exists, and if so import it (optional)
    video_path = ""
    if os.path.exists(os.path.join("custom", "videos", f"{song_id}.mp4")):
        video_path = os.path.join("custom", "videos", f"{song_id}.mp4")
    elif os.path.exists(os.path.join(contents_dir, "data", "movie", f"{song_id}.mp4")):
        video_path = os.path.join(
            contents_dir, "data", "movie", f"{song_id}.mp4")
    else:
        warning("No video found, I hope you know what you're doing!")

    if video_path != "":
        print(
            f"Found video file {os.path.basename(video_path)}, importing it...")
        shutil.copy(video_path, output_path)
        video_path = os.path.join(str(
            song_id), os.path.basename(video_path))
        starter_bmson["bga"]["bga_events"] = [{"id": 1, "y": 0}]
        starter_bmson["bga"]["bga_header"] = [
            {"id": 1, "name": os.path.basename(video_path)}]

    # Internal files

    # import all relevant files
    sound_path = ""
    if os.path.exists(os.path.join(contents_dir, "data", "sound", song_id)):
        sound_path = os.path.join(contents_dir, "data", "sound", song_id)
    elif os.path.exists(os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", song_id)):
        sound_path = os.path.join(contents_dir, "data", "sound", f"{song_id}_ifs", song_id)
    else:
        error("Invalid sound path, exiting...")

    for _, _, filenames in os.walk(os.path.join(".", sound_path)):
        for file in filenames:
            shutil.copy(os.path.join(".", sound_path, file), output_path)
            print(f"{os.path.basename(file)} imported.")

    # check if chart file path exists (REQUIRED)
    chart_path = ""
    if os.path.exists(os.path.join(".", "out", song_id, f"{song_id}.1")):
        chart_path = os.path.join(".", "out", song_id, f"{song_id}.1")
        print(f"Found chart file {os.path.basename(chart_path)}.")
    else:
        error("Invalid chart path, exiting...")

    # check if song container path exists
    container_path = ""
    if os.path.exists(os.path.join(".", "out", song_id, f"{song_id}.2dx")):
        container_path = os.path.join(".", "out", song_id, f"{song_id}.2dx")
        print(f"Found container file {os.path.basename(container_path)}.")
    elif os.path.exists(os.path.join(".", "out", song_id, f"{song_id}.s3p")):
        container_path = os.path.join(".", "out", song_id, f"{song_id}.s3p")
        print(f"Found container file {os.path.basename(container_path)}.")
    else:
        print("Container file not yet found, circling back later.")

    # check if song preview path exists, and if so import it (REQUIRED)
    if os.path.exists(os.path.join(".", "out", song_id, f"{song_id}_pre.2dx")):
        preview_path = os.path.join(".", "out", song_id, f"{song_id}_pre.2dx")
        print(f"Found preview file {os.path.basename(preview_path)}.")
    else:
        error("Invalid preview path, exiting...")

    # extract audio preview
    extracted_preview_path = \
        get_audio_samples_from_container(song_id,
                                         os.path.join(".", "out", str(song_id), os.path.basename(preview_path)))[0]
    starter_bmson["info"]["preview_music"] = os.path.join(
        song_id, os.path.basename(extracted_preview_path))

    # parse chart directory entries
    with open(chart_path, 'rb') as chart_file:
        chart_directory = []
        file_offset = 0
        for i in range(12):
            chart_file.seek(file_offset)
            chart_directory.append(struct.unpack("<I", chart_file.read(4))[0])
            file_offset += 8

        # iterate over all (existing) charts found inside chart file
        # but for now, we start with the SP-HYPER chart
        for i in range(len(chart_directory)):
            # Find out if a chart is not supposed to exist in the db
            chart_level_is_zero = False

            if str(i) in chart_names:
                match (chart_names[str(i)]):
                    case "SP-H": 
                        if db_entry["SPH_level"] == 0: chart_level_is_zero = True
                    case "SP-N": 
                        if db_entry["SPN_level"] == 0: chart_level_is_zero = True
                    case "SP-A": 
                        if db_entry["SPA_level"] == 0: chart_level_is_zero = True
                    case "SP-B": 
                        if db_entry["SPB_level"] == 0: chart_level_is_zero = True
                    case "SP-L": 
                        if db_entry["SPL_level"] == 0: chart_level_is_zero = True
                    case "DP-H": 
                        if db_entry["DPH_level"] == 0: chart_level_is_zero = True
                    case "DP-N": 
                        if db_entry["DPN_level"] == 0: chart_level_is_zero = True
                    case "DP-A": 
                        if db_entry["DPA_level"] == 0: chart_level_is_zero = True
                    case "DP-B": 
                        if db_entry["DPB_level"] == 0: chart_level_is_zero = True
                    case "DP-L": 
                        if db_entry["DPL_level"] == 0: chart_level_is_zero = True
                    case _:
                        continue

                if not chart_level_is_zero:
                    # work around song-specific bug for SP-N and DP-N charts
                    if song_id == '30100' and i in [1, 7]:
                        continue
                    parse_chart(contents_dir, song_id, db_entry, chart_file,
                                chart_directory[i], i, container_path)

    # we're done with source files, remove them from output directory
    for _, _, filenames in os.walk(output_path):
        for file in filenames:
            (_, extension) = os.path.splitext(file)
            if extension == ".1" or extension == ".2dx" or extension == ".s3p":
                os.remove(os.path.join(output_path, file))
                print(f"{file} deleted.")

    # append ASCII title to folder
    safe_folder_name = output_path + " - " + db_entry["title_ascii"]
    # replace reserved characters with underscore
    reserved_chars = r'[<>:"\\|?*]'
    safe_folder_name = re.sub(reserved_chars, '_', safe_folder_name)
    # remove trailing dots and spaces
    safe_folder_name = "." + safe_folder_name.rstrip('. ').lstrip('. ')
    os.rename(output_path, safe_folder_name)
    success(f"Renamed output directory to {os.path.basename(safe_folder_name)}.")
