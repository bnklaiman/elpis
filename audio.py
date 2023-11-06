import os
from pydub import AudioSegment
import struct
import subprocess
import torch
import torchaudio
from Misc_enums import *

from utils import *

def is_silent(file_path, threshold_db=-60):
    audio = AudioSegment.from_file(file_path)
    max_amplitude_db = audio.max_dBFS
    return max_amplitude_db <= threshold_db


def trim_start_silence(file_path):
    audio = AudioSegment.from_file(file_path, format="ogg")

    portion_to_remove = 8  # milliseconds
    audio_without_portion = audio[portion_to_remove:]

    audio_without_portion.export(file_path, format="ogg")
    print(f"Trimmed the first {portion_to_remove}ms of silence from {os.path.basename(file_path)}.")


def get_audio_samples_from_container(song_id, container, volume_multiplier=1):
    print(f"Looking at file {container} in song id #{song_id}")

    [container_id, container_extension] = os.path.basename(
        container).split(".")

    # if preview file detected, remove "_pre" from the path name
    is_preview_file = False
    container_id_length = len(container_id)
    if container_id[container_id_length - 4:container_id_length] == "_pre":
        container_id = container_id.split("_")[0]
        is_preview_file = True

    # initial check if file extension is legit-- actual contents will be checked later
    if container_extension == "2dx":
        print(".2dx file detected (probably)")
    elif container_extension == "s3p":
        print(".s3p file detected (probably)")
    else:
        error("Invalid or nonexistent file type detected, exiting...")

    with open(container, "rb") as infile:
        print(f"{os.path.basename(infile.name)} loaded successfully.")

        # create output directory if it doesn't exist yet
        output_path = f"{os.path.join('.', 'out', str(song_id), str(container_id))}"
        if os.path.exists(output_path):
            print(f"Output path {output_path} already exists, using it.")
        else:
            os.makedirs(output_path)
            print(f"Output path {output_path} created.")

        # get the number of files within the container
        if container_extension == "2dx":
            infile.seek(0x14)
        elif container_extension == "s3p":
            infile.seek(0x04)

        file_count = struct.unpack("<I", infile.read(4))[0]
        print(f"{file_count} files detected inside {os.path.basename(infile.name)}.")

        # initialize sound channels array for export at the end
        sound_channels = []

        # iterate over each audio sample in the container
        for i in range(file_count):
            if container_extension == "2dx":
                infile.seek(0x48 + i * 4)
            elif container_extension == "s3p":
                infile.seek(i * 8 + 8)
            else:
                error("Invalid or nonexistent file type detected, exiting...")

            offset = struct.unpack("<I", infile.read(4))[0]

            # check if each audio sample contained within is valid
            infile.seek(offset)
            magic_string = infile.read(4)
            if container_extension == "2dx" and magic_string != b'2DX9':
                error("Not a valid 2DX audio file, exiting...")
            elif container_extension == "s3p" and magic_string != b'S3V0':
                error("Not a valid S3V audio file, exiting...")

            # init
            offset += 4
            infile.seek(offset)
            data_offset = struct.unpack("<I", infile.read(4))[0] - 8
            offset += 4
            infile.seek(offset)
            data_size = struct.unpack("<I", infile.read(4))[0]

            # capture and save the audio sample itself
            offset += data_offset
            infile.seek(offset)
            audio_bytes = infile.read(data_size)

            if container_extension == "2dx":
                audio_extension = "wav"
            elif container_extension == "s3p":
                audio_extension = "wma"
            else:
                error("Invalid container extension, exiting...")

            if is_preview_file:
                filename = f"{os.path.join(output_path, f'preview.{audio_extension}')}"
            else:
                filename = f"{os.path.join(output_path, f'{i:04d}.{audio_extension}')}"

            if os.path.exists(filename):
                print(f"Extracted file {os.path.basename(filename)} already exists, skipping...")
            else:
                with open(filename, 'wb') as outfile:
                    outfile.write(audio_bytes)

                print(f"{os.path.basename(filename)}: {len(audio_bytes)} bytes written.")

        print("All audio samples extracted.")
        for filename in os.listdir(output_path):
            if filename.endswith(".wav") or filename.endswith(".wma"):
                sound_channels.append(convert_to_ogg_file(os.path.join(output_path, filename), song_id, volume_multiplier))

        sound_channels.sort()
        print("All sound channels exported.")
        return sound_channels


def convert_to_ogg_file(infile, song_id, volume_multiplier):
    outfile = os.path.splitext(infile)[0] + ".ogg"
    
    # Figure out whether to cut out the silence of converted audio files
    should_be_trimmed = False

    if song_id >= "25002" and song_id not in songs_with_s3p_to_not_trim:
        should_be_trimmed = True

    # the actual conversion happens here
    if os.path.exists(outfile):
        print(
            f"Converted file {os.path.basename(outfile)} already exists, skipping...")
    else:
        print(f"Converting to {os.path.basename(outfile)}...")
        
        ffmpeg_command = ["ffmpeg", "-i", infile, "-filter:a", f"volume={volume_multiplier}", "-c:a", "libvorbis", "-q:a", "9", "-shortest"]
        if should_be_trimmed:
            ffmpeg_command = ffmpeg_command + ["-af", "atrim=start=0.0925"]
        ffmpeg_command = ffmpeg_command + ["-vn", "-v", "quiet", "-y", outfile]
        subprocess.run(ffmpeg_command, check=True)

        # if is_silent(outfile):

    
    os.remove(infile)

    return os.path.join(os.path.abspath(outfile).split(os.path.sep)[-2], os.path.abspath(outfile).split(os.path.sep)[-1])


# given a list of audio samples and their offsets, output a single audio file containing all merged background samples played at the correct time
def generate_bgm(bgm_samples, song_id, dir_index):
    output_folder = bgm_samples[0][1].split(os.path.sep)[0]

    # Determine file name from chart directory entry
    filename = f"{output_folder}-BGM-"
    match dir_index:
        case 0:
            filename += "SP-H"
        case 1:
            filename += "SP-N"
        case 2:
            filename += "SP-A"
        case 3:
            filename += "SP-B"
        case 4:
            filename += "SP-L"
        case 6:
            filename += "DP-H"
        case 7:
            filename += "DP-N"
        case 8:
            filename += "DP-A"
        case 9:
            filename += "DP-B"
        case 10:
            filename += "DP-L"
        case _:
            error("Invalid directory index, exiting...")

    filename += ".ogg"
    bgm_output_location = os.path.join(".", "out", str(song_id),
                                       output_folder, filename)

    if os.path.exists(filename):
        print(f"File {os.path.basename(filename)} already exists, skipping.")
    else:
        max_length = 0
        for offset, file in bgm_samples:
            print(
                f"Torchaudio: Placing file {os.path.basename(file)} at offset {offset}ms.")
            file = os.path.join(".", "out", str(song_id), file)
            signal, sample_rate = torchaudio.load(file)
            signal_length = int(
                signal.shape[1] * 44100 / sample_rate + offset * 44100 / 1000)
            if signal_length > max_length:
                max_length = signal_length
        print("Torchaudio: Initial pass complete.")
        output_signal = torch.zeros(2, max_length)

        for offset, file in bgm_samples:
            file = os.path.join(".", "out", str(song_id), file)
            print(
                f"Torchaudio: Merging file {os.path.basename(file)} at offset {offset}ms.")
            signal, sample_rate = torchaudio.load(file)
            signal = torchaudio.transforms.Resample(sample_rate, 44100)(signal)
            if signal.shape[0] == 1:
                signal = torch.cat((signal, signal), dim=0)
            start_sample = int(offset * 44100 / 1000)
            end_sample = start_sample + signal.shape[1]
            output_signal[:, start_sample:end_sample] += signal
        print("Torchaudio: Final pass complete.")
        print(f"Saving to file {os.path.basename(filename)}...")
        torchaudio.save(bgm_output_location, output_signal, 44100, True, 9, "ogg")
        print(f"File {os.path.basename(filename)} saved.")

    return os.path.join(str(output_folder), filename)