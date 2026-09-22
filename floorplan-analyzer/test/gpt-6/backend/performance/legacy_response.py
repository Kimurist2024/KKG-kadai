"""補正ゼロの新規フィールドを検証し、凍結版と比較する出力を返す。"""
import copy
import struct


def without_openings(data):
    data = copy.deepcopy(data)
    if 'settings' in data:
        assert data['settings'].pop('door_opening_depth_m') == 0
    if 'summary' in data:
        assert data['summary'].pop('door_opening_adjusted_room_count') == 0
    for room in data['rooms']:
        assert struct.pack('!d', room.pop('floor_area_raw_m2')) == struct.pack('!d', room['floor_area_m2'])
        assert struct.pack('!d', room.pop('door_opening_adjustment_m2')) == struct.pack('!d', 0.0)
        assert room.pop('door_opening_transfers') == []
    return data
