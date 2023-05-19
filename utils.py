import os


def sanitize_input(data):
    if data != data:  # this checks for misc. NaNs
        data = ""

    data = data.replace(u'\xa0', u' ')
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


# alt_containers = {
#     '01000': {
#         0: "010001.2dx",
#         1: "010001.2dx",
#         2: "01000a.2dx",
#         6: "010001.2dx",
#         7: "010001.2dx",
#         8: "01000a.2dx"
#     },
#     '01001': {
#         0: "010011.2dx",
#         1: "010011.2dx",
#         2: "010012.2dx",
#         6: "010011.2dx",
#         7: "010011.2dx",
#         8: "010012.2dx"
#     },
#     '01002': {
#         0: "010021.2dx",
#         1: "010021.2dx",
#         2: "010022.2dx",
#         6: "010021.2dx",
#         7: "010021.2dx",
#         8: "010022.2dx"
#     },
#     '01003': {
#         0: "010031.2dx",
#         1: "010031.2dx",
#         2: "010032.2dx",
#         6: "010031.2dx",
#         7: "010031.2dx",
#         8: "010032.2dx"
#     },
#     '01004': {
#         0: "010041.2dx",
#         1: "010041.2dx",
#         2: "010041.2dx",
#         6: "010041.2dx",
#         7: "010041.2dx",
#         8: "010041.2dx"
#     },
#     '01005': {
#         0: "010051.2dx",
#         1: "010051.2dx",
#         2: "010052.2dx",
#         6: "010051.2dx",
#         7: "010051.2dx",
#         8: "010052.2dx"
#     },
#     '01006': {
#         0: "01006.2dx",
#         1: "01006.2dx",
#         2: "01006.2dx",
#         6: "010062.2dx",
#         7: "010062.2dx",
#         8: "010062.2dx"
#     },
#     '01008': {
#         0: "01008.2dx",
#         1: "01008.2dx",
#         2: "01008a.2dx",
#         6: "01008.2dx",
#         7: "01008.2dx",
#         8: "01008a.2dx"
#     },
#     '01204': {
#         0: "01204.2dx",
#         1: "01204.2dx",
#         2: "012041.2dx",
#         6: "01204.2dx",
#         7: "01204.2dx",
#         8: "012041.2dx"
#     },
#     '02000': {
#         0: "020001.2dx",
#         1: "020001.2dx",
#         2: "020002.2dx",
#         6: "020001.2dx",
#         7: "020001.2dx",
#         8: "020002.2dx"
#     },
#     '06000': {
#         0: "060001.2dx",
#         1: "060001.2dx",
#         2: "060001.2dx",
#         6: "060002.2dx",
#         7: "060002.2dx",
#         8: "060002.2dx",
#     },
#     '06028': {
#         0: "060281.2dx",
#         1: "060281.2dx",
#         2: "060282.2dx",
#         6: "060281.2dx",
#         7: "060281.2dx",
#         8: "060282.2dx"
#     },
#     '18051': {
#         0: "18051h.2dx",
#         1: "18051.2dx",
#         2: "18051a.2dx",
#         6: "18051h.2dx",
#         7: "18051.2dx",
#         8: "18051a.2dx",
#     },
#     '24084': {
#         # 240841.2dx: VENUS mix
#         # 240842.2dx: Ryu* mix
#         # 240843.2dx: kors k mix
#         # 240844.2dx: Prim version
#         # 240845.2dx: original mix
#         0: "240841.2dx",
#         1: "240845.2dx",
#         2: "240842.2dx",
#         6: "240843.2dx",
#         7: "240845.2dx",
#         8: "240844.2dx"
#     },
#     '28102': {
#         0: "28102.s3p",
#         1: "28102.s3p",
#         2: "28102a.s3p",
#         6: "28102.s3p",
#         7: "28102.s3p",
#         8: "28102a.s3p"
#     }
# }
