def intervals_overlap(start1, end1, start2, end2):
    return start1 < end2 and start2 < end1
