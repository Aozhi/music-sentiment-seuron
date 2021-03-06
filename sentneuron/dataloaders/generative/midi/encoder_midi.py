# External imports
import os
import math    as ma
import numpy   as np
import music21 as m21

from abc import ABC, abstractmethod

# Local imports
from ..encoder import Encoder

THREE_DOTTED_BREVE = 15
THREE_DOTTED_32ND  = 0.21875

MIN_VELOCITY = 0
MAX_VELOCITY = 128

MIN_TEMPO = 24
MAX_TEMPO = 160

MAX_PITCH = 128

class EncoderMidi(Encoder):
    def load(self, datapath, sample_freq=4, piano_range=(33, 93), modulate_range=10, stretching_range=10, invert=False, retrograde=False):
        encoded_midi = []

        vocab = set()

        # Read every file in the given directory
        for file in os.listdir(datapath):
            midipath = os.path.join(datapath, file)

            # Check if it is not a directory and if it has either .midi or .mid extentions
            if os.path.isfile(midipath) and (midipath[-5:] == ".midi" or midipath[-4:] == ".mid"):
                print("Parsing midi file:", midipath)

                # Split datapath into dir and filename
                midi_dir = "/".join(midipath.split("/")[:-1])
                midi_name = midipath.split("/")[-1].split(".")[0]

                # If txt version of the midi already exists, load data from it
                midi_txt_name = midi_dir + "/" + midi_name + ".txt"
                if(os.path.isfile(midi_txt_name)):
                    midi_fp = open(midi_txt_name, "r")
                    midi_content = midi_fp.read()
                else:
                    # Create a music21 stream and open the midi file
                    midi = m21.midi.MidiFile()
                    midi.open(midipath)
                    midi.read()
                    midi.close()

                    # Translate midi to stream of notes and chords
                    midi_content = self.midi2encoding(midi, sample_freq, piano_range, modulate_range, stretching_range, invert, retrograde)

                    if len(midi_content) > 0:
                        midi_fp = open(midi_txt_name, "w+")
                        midi_fp.write(midi_content)
                        midi_fp.flush()

                midi_fp.close()

                if len(midi_content) > 0:
                    encoded_midi.append((midi_txt_name, midi_name + ".mid"))

                    # Remove empty character if it exists after the split
                    words = set(midi_content.split(" "))
                    if "" in words:
                        words.remove("")

                    vocab = vocab | words

        return encoded_midi, vocab

    @abstractmethod
    def midi2encoding(self, midi, sample_freq, piano_range, modulate_range, stretching_range, invert, retrograde):
        pass

    @abstractmethod
    def encoding2midi(self, encoded_midi):
        pass

    def decode(self, ixs):
        # Create piano roll and return it
        return " ".join(self.ix_to_symbol[ix] for ix in ixs)

    def read(self, filepath):
        fp = open(filepath, "r")
        content = fp.read()
        content = content.split(" ")
        content = list(filter(('').__ne__, content))
        fp.close()
        return content

    def write(self, encoded_midi, path):
        # Base class checks if output path exists
        midi = self.encoding2midi(encoded_midi)
        midi.open(path + ".mid", "wb")
        midi.write()
        midi.close()

    def str2symbols(self, s):
        return s.split(" ")

    def midi_parse_notes(self, midi_stream, sample_freq):
        note_filter = m21.stream.filters.ClassFilter('Note')

        note_events = []
        for note in midi_stream.recurse().addFilter(note_filter):
            pitch    = note.pitch.midi
            duration = note.duration.quarterLength
            velocity = note.volume.velocity
            offset   = ma.floor(note.offset * sample_freq)

            note_events.append((pitch, duration, velocity, offset))

        return note_events

    def midi_parse_chords(self, midi_stream, sample_freq):
        chord_filter = m21.stream.filters.ClassFilter('Chord')

        note_events = []
        for chord in midi_stream.recurse().addFilter(chord_filter):
            pitches_in_chord = chord.pitches
            for pitch in pitches_in_chord:
                pitch    = pitch.midi
                duration = chord.duration.quarterLength
                velocity = chord.volume.velocity
                offset   = ma.floor(chord.offset * sample_freq)

                note_events.append((pitch, duration, velocity, offset))

        return note_events

    def midi_parse_metronome(self, midi_stream, sample_freq):
        metronome_filter = m21.stream.filters.ClassFilter('MetronomeMark')

        time_events = []
        for metro in midi_stream.recurse().addFilter(metronome_filter):
            time = int(metro.number)
            offset = ma.floor(metro.offset * sample_freq)
            time_events.append((time, offset))

        return time_events

    def midi2notes(self, midi_stream, sample_freq, modulate_range, invert):
        notes = []
        notes += self.midi_parse_notes(midi_stream, sample_freq)
        notes += self.midi_parse_chords(midi_stream, sample_freq)

        # Transpose the notes to all the keys in modulate_range
        transpositions = self.transpose_notes(notes, modulate_range)

        # Invert notes
        inversions = []
        if invert:
            inversions = [self.invert_notes(t) for t in transpositions]

        return transpositions + inversions

    def midi2piano_roll(self, midi_stream, sample_freq, piano_range, modulate_range, invert=False, retrograde=False):
        # Calculate the amount of time steps in the piano roll
        time_steps = ma.floor(midi_stream.duration.quarterLength * sample_freq) + 1

        # Parse the midi file into a list of notes (pitch, duration, velocity, offset)
        transpositions = self.midi2notes(midi_stream, sample_freq, modulate_rang, invert)
        return self.notes2piano_roll(transpositions, time_steps, piano_range)

    def midi2piano_roll_with_performance(self, midi_stream, sample_freq, piano_range, modulate_range, stretching_range, invert=False, retrograde=False):
        # Calculate the amount of time steps in the piano roll
        time_steps = ma.floor(midi_stream.duration.quarterLength * sample_freq) + 1

        # Parse the midi file into a list of notes (pitch, duration, velocity, offset)
        transpositions = self.midi2notes(midi_stream, sample_freq, modulate_range, invert)

        time_events = self.midi_parse_metronome(midi_stream, sample_freq)
        time_streches = self.strech_time(time_events, stretching_range)

        performances = self.notes2piano_roll_performances(transpositions, time_streches, time_steps, piano_range)

        retrograde_performances = []
        if retrograde:
            for perm in performances:
                retrograde_perm = np.flip(perm, 0)
                retrograde_performances.append(retrograde_perm)

        return performances + retrograde_performances

    def notes2piano_roll(self, transpositions, time_steps, piano_range):
        scores = []

        min_pitch, max_pitch = piano_range
        for t_ix in range(len(transpositions)):
            # Create piano roll with calcualted size
            piano_roll = np.zeros((time_steps, MAX_PITCH))

            for note in transpositions[t_ix]:
                pitch, duration, velocity, offset = n

                # Force notes to be inside the specified piano_range
                pitch = self.__clamp_pitch(pitch, max_pitch, min_pitch)

                piano_roll[offset, pitch] = 1

            scores.append(piano_roll)

        return piano_roll

    def notes2piano_roll_performances(self, transpositions, time_streches, time_steps, piano_range):
        performances = []

        min_pitch, max_pitch = piano_range
        for t_ix in range(len(transpositions)):
            for s_ix in range(len(time_streches)):
                # Create piano roll with calcualted size.
                # Add one dimension to very entry to store velocity and duration.
                piano_roll = np.zeros((time_steps, MAX_PITCH + 1, 2))

                for note in transpositions[t_ix]:
                    pitch, duration, velocity, offset = note
                    if duration == 0.0:
                        continue

                    # Force notes to be inside the specified piano_range
                    pitch = self.__clamp_pitch(pitch, max_pitch, min_pitch)

                    piano_roll[offset, pitch][0] = self.__clamp_duration(duration)
                    piano_roll[offset, pitch][1] = self.discretize_value(velocity, bins=32, range=(MIN_VELOCITY, MAX_VELOCITY))

                for time_event in time_streches[s_ix]:
                    time, offset = time_event
                    piano_roll[offset, -1][0] = self.discretize_value(time, bins=100, range=(MIN_TEMPO, MAX_TEMPO))

                performances.append(piano_roll)

        return performances

    def transpose_notes(self, notes, modulate_range):
        transpositions = []

        # Modulate the piano_roll for other keys
        first_key = -ma.floor(modulate_range/2)
        last_key  =  ma.ceil(modulate_range/2)

        for key in range(first_key, last_key):
            notes_in_key = []
            for n in notes:
                pitch, duration, velocity, offset = n
                t_pitch = pitch + key
                notes_in_key.append((t_pitch, duration, velocity, offset))
            transpositions.append(notes_in_key)

        return transpositions

    def strech_time(self, time_events, stretching_range):
        streches = []

        # Modulate the piano_roll for other keys
        slower_time = -ma.floor(stretching_range/2)
        faster_time =  ma.ceil(stretching_range/2)

        # Modulate the piano_roll for other keys
        for t_strech in range(slower_time, faster_time):
            time_events_in_strech = []
            for t_ev in time_events:
                time, offset = t_ev
                s_time = time + 0.05 * t_strech * MAX_TEMPO
                time_events_in_strech.append((s_time, offset))
            streches.append(time_events_in_strech)

        return streches

    def invert_notes(self, notes, max_pitch = 127):
        inverted_notes = []

        for note in notes:
            pitch, duration, velocity, offset = note
            inverted_notes.append((max_pitch - pitch, duration, velocity, offset))

        return inverted_notes

    def discretize_value(self, val, bins, range):
        min_val, max_val = range

        val = int(max(min_val, val))
        val = int(min(val, max_val))

        bin_size = (max_val/bins)
        return ma.floor(val/bin_size) * bin_size

    def __clamp_pitch(self, pitch, max, min):
        while pitch < min:
            pitch += 12
        while pitch >= max:
            pitch -= 12
        return pitch

    def __clamp_duration(self, duration, max=THREE_DOTTED_BREVE, min=THREE_DOTTED_32ND):
        # Max duration is 3-dotted breve
        if duration > max:
            duration = max

        # min duration is 3-dotted breve
        if duration < min:
            duration = min

        duration_tuple = m21.duration.durationTupleFromQuarterLength(duration)
        if duration_tuple.type == "inexpressible":
            duration_clossest_type = m21.duration.quarterLengthToClosestType(duration)[0]
            duration = m21.duration.typeToDuration[duration_clossest_type]

        return duration
