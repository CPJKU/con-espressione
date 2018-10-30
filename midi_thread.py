"""
    Threading class for MIDI playback.

TODO
----
* Move decoding procedure to basismixer.performance_codec to make
BasisMixerMidiThread more modular.
* Add melody lead.
"""
import threading
import time
import mido
import numpy as np

from mido import Message

from basismixer.performance_codec import load_bm_preds


class MidiThread(threading.Thread):
    def __init__(self, midi_path, midi_port):
        threading.Thread.__init__(self)
        self.midi = midi_path
        self.midi_port = midi_port
        self.vel = None
        self.tempo = 1

    def set_velocity(self, vel):
        self.vel = vel

    def set_tempo(self, tempo):
        self.tempo = tempo

    def run(self):
        with mido.open_output(self.midi_port) as outport:
            for msg in mido.MidiFile(self.midi):
                play_msg = msg
                if msg.type == 'note_on':
                    if msg.velocity != 0 and self.vel is not None:
                        play_msg = msg.copy(velocity=self.vel)

                time.sleep(play_msg.time*self.tempo)

                outport.send(play_msg)


class BasisMixerMidiThread(threading.Thread):
    def __init__(self, bm_precomputed_path, midi_port,
                 vel_min=30, vel_max=110, deadpan=False):
        threading.Thread.__init__(self)
        self.midi_port = midi_port
        self.vel = 64
        self.tempo = 1
        # Construct score-performance dictionary
        self.score_dict = load_bm_preds(bm_precomputed_path,
                                        deadpan=deadpan)

        # Minimal and Maximal MIDI velocities allowed for each note
        self.vel_min = vel_min
        self.vel_max = vel_max

    def set_velocity(self, vel):
        self.vel = vel

    def set_tempo(self, tempo):
        self.tempo = tempo

    def run(self):
        # Get unique score positions (and sort them)
        unique_onsets = np.array(list(self.score_dict.keys()))
        unique_onsets.sort()

        # Initialize playback after 0.5 seconds
        prev_eq_onset = 0.5

        # Initial time
        init_time = time.time()

        # Initialize list for note off messages
        off_messages = []

        # Open port
        with mido.open_output(self.midi_port) as outport:

            # iterate over score positions
            for on in unique_onsets:

                # Get score and performance info
                (pitch, ioi, dur,
                 vt, vd, lbpr,
                 tim, lart, mel) = self.score_dict[on]

                # TODO:
                # * Scale expressive parameters
                # * add external controller (PowerMate)

                # update tempo and dynamics from the controller
                bpr_a = self.tempo
                vel_a = self.vel

                # Compute equivalent onset
                eq_onset = prev_eq_onset + (2 ** lbpr) * bpr_a * ioi

                # Update previous equivalent onset
                prev_eq_onset = eq_onset

                # Compute onset for all notes in the current score position
                perf_onset = eq_onset - tim
                # indices of the notes in the score position according to
                # their onset
                perf_onset_idx = np.argsort(perf_onset)

                # Sort performed onsets
                perf_onset = perf_onset[perf_onset_idx]

                # Sort pitch
                pitch = pitch[perf_onset_idx]
                # Compute performed duration for each note (and sort them)
                perf_duration = ((2 ** lart) * bpr_a * dur)[perf_onset_idx]

                # Compute performed MIDI velocity for each note (and sort them)
                perf_vel = np.clip(np.round((vt * vel_a - vd)),
                                   self.vel_min,
                                   self.vel_max).astype(np.int)[perf_onset_idx]

                # Initialize list of note on messages
                on_messages = []

                for p, o, d, v in zip(pitch, perf_onset,
                                      perf_duration, perf_vel):

                    # Create note on message (the time attribute corresponds to
                    # the time since the beginning of the piece, not the time
                    # since the previous message)
                    on_msg = Message('note_on', velocity=v, note=p, time=o)

                    # Create note off message (the time attribute corresponds
                    # to the time since the beginning of the piece)
                    off_msg = Message('note_off', velocity=v, note=p, time=o+d)

                    # Append the messages to their corresponding lists
                    on_messages.append(on_msg)
                    off_messages.append(off_msg)

                # Sort list of note off messages by offset time
                off_messages.sort(key=lambda x: x.time)

                # Send otuput MIDI messages
                while len(on_messages) > 0:

                    # Send note on messages
                    # Get current time
                    current_time = time.time() - init_time
                    if current_time >= on_messages[0].time:
                        # Send current note on message
                        outport.send(on_messages[0])
                        # delete note on message from the list
                        del on_messages[0]

                    # If there are note off messages, send them
                    if len(off_messages) > 0:
                        # Update current time
                        current_time = time.time() - init_time
                        if current_time >= off_messages[0].time:
                            # Send current note off message
                            outport.send(off_messages[0])
                            # delete note off message from the list
                            del off_messages[0]

                    # sleep for a little bit...
                    time.sleep(1e-3)

            # Send remaining note off messages
            while len(off_messages) > 0:
                current_time = time.time() - init_time
                if current_time >= off_messages[0].time:
                    outport.send(off_messages[0])
                    del off_messages[0]