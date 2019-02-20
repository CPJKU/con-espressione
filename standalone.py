"""
    Run the Demo
"""
import os
import mido
from midi_thread import BMThread
import platform


class LeapControl():
    def __init__(self, config, song_list):
        self.midi_outport = mido.open_output('LeapControl', virtual=True)
        self.midi_inport =  mido.open_input('LeapControl', virtual=True)

        self.song_list = song_list
        self.cur_song_id = 0
        self.cur_song = self.song_list[self.cur_song_id]

        # init playback thread
        self.playback_thread = None

    def select_song(self, val):
        val = int(val)

        if val < len(self.song_list):
            self.cur_song_id = int(val)
            self.cur_song = self.song_list[self.cur_song_id]

    def play(self):
        # terminate playback thread if running
        if self.playback_thread != None:
            self.playback_thread.join()

        # init playback thread
        self.playback_thread = BMThread(self.cur_song, midi_out=self.midi_outport)
        self.playback_thread.set_tempo(1.0)
        self.playback_thread.set_scaler(0.0)
        self.playback_thread.set_velocity(50.0)

        self.playback_thread.start()

    def stop(self):
        if self.playback_thread != None:
            self.playback_thread.stop_playing()

    def set_velocity(self, val):
        # scale value in [0, 127] to [0.5, 2]
        if val <= 64:
            out = (0.5 / 64.0) * val + 0.5
        if val > 64:
            out = (2.0 / 127.0) * val

        self.playback_thread.set_velocity(out)

    def set_tempo(self, val):
        # scale value in [0, 127] to [0.5, 2]
        if val <= 64:
            out = - (2.0 / 128.0) * val + 2.0
        if val > 64:
            out = - (1.0 / 127.0) * val + 1.5

        self.playback_thread.set_tempo(out)

    def set_ml_scaler(self, val):
        # scale value in [0, 127] to [0, 100]
        out = (100 / 127) * val

        self.playback_thread.set_scaler(out)

    def parse_midi_msg(self, msg):
        if msg.type == 'control_change':
            if msg.channel == 0:
                if msg.control == 20:
                    # tempo
                    self.set_tempo(float(msg.value))
                if msg.control == 21:
                    # velocity
                    self.set_velocity(float(msg.value))
                if msg.control == 22:
                    # ml-scaler
                    self.set_ml_scaler(float(msg.value))
                if msg.control == 23:
                    # select song
                    print('Received Song change. New value: {}'.format(msg.value))
                    self.select_song(int(msg.value))
                if msg.control == 24:
                    # start playing
                    print('Received Play command. New value: {}'.format(msg.value))
                    if int(msg.value) == 127:
                        self.play()
                if msg.control == 25:
                    # stop playing
                    print('Received Stop command. New value: {}'.format(msg.value))
                    if int(msg.value) == 127:
                        self.stop()


def main():
    CONFIG = {'playmode': 'BM',
              'driver': 'alsa' if platform.system() == 'Linux' else 'coreaudio',
              'control': 'Mouse',
              'bm_file': 'bm_files/beethoven_op027_no2_mv1_bm_z.txt',
              'bm_config': 'bm_files/beethoven_op027_no2_mv1_bm_z.json'}

    SONG_LIST = ['bm_files/beethoven_op027_no2_mv1_bm_z.txt',
                 'bm_files/chopin_op10_No3_bm_magaloff.txt']

    # instantiate LeapControl
    lc = LeapControl(CONFIG, SONG_LIST)

    try:
        # listen to input MIDI port for messages
        for msg in lc.midi_inport:
            lc.parse_midi_msg(msg)

    except KeyboardInterrupt:
        print('Received keyboard interrupt. Shutting down...')

    finally:
        # clean-up
        lc.stop()
        lc.playback_thread.join()
        lc.midi_outport.close()
        lc.midi_inport.close()


if __name__ == '__main__':
    main()
