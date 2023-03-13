import os

from elpis import parse_all_charts_and_audio


def main():
    contents_dir = os.path.join(
        "..", "..", "Rhythm Games", "LDJ-2022103100", "contents")
    parse_all_charts_and_audio(contents_dir, 20003, True)


if __name__ == "__main__":
    main()
