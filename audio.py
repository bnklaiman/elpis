import os
import struct
import subprocess
import sys


def get_audio_samples_from_container(song_id: int, container: str):
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
        sys.exit("Invalid or nonexistent file type detected, exiting...")

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
                sys.exit("Invalid or nonexistent file type detected, exiting...")

            offset = struct.unpack("<I", infile.read(4))[0]

            # check if each audio sample contained within is valid
            infile.seek(offset)
            magic_string = infile.read(4)
            if container_extension == "2dx" and magic_string != b'2DX9':
                sys.exit("Not a valid 2DX audio file, exiting...")
            elif container_extension == "s3p" and magic_string != b'S3V0':
                sys.exit("Not a valid S3V audio file, exiting...")

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

            if is_preview_file:
                filename = f"{os.path.join(output_path, f'preview.{audio_extension}')}"
            else:
                filename = f"{os.path.join(output_path, f'{i:04d}.{audio_extension}')}"

            with open(filename, 'wb') as outfile:
                outfile.write(audio_bytes)

            print(f"{os.path.basename(filename)}: {len(audio_bytes)} bytes written.")

        print("All audio samples extracted.")
        for filename in os.listdir(output_path):
            if filename.endswith(".wav") or filename.endswith(".wma"):
                sound_channels.append(convert_to_ogg_file(
                    os.path.join(output_path, filename)))

        sound_channels.sort()
        print("All sound channels exported.")
        return sound_channels


def convert_to_ogg_file(infile: str):
    outfile = os.path.splitext(infile)[0] + ".ogg"

    # the actual conversion happens here
    if os.path.exists(outfile):
        print(
            f"Converted file {os.path.basename(outfile)} already exists, skipping...")
    else:
        print(f"Converting to {os.path.basename(outfile)}...")
        subprocess.run(["ffmpeg", "-i", infile, "-c:a", "libvorbis",
                        "-q:a", "5", "-v", "8", "-y", outfile], check=True)
    os.remove(infile)

    return os.path.join(os.path.abspath(outfile).split('/')[-2], os.path.abspath(outfile).split('/')[-1])


# Input: array of sound channels (from BMSON_ROOT["sound_channels"])
# in all sound channels, add all notes where x = 0 to new array
# taking into account y in 1/240 pulses, convert to ms for merging using python audio library
# Output: single audio file containing all merged background samples played at the correct time