import json
import re
import numpy as np

from abc import ABC, abstractmethod

class Encoder(ABC):
    def __init__(self, datapath=None, vocab=None, data=None, name="sentneuron"):
        self.name = name

        if datapath != None:
            self.data, self.vocab = self.load(datapath)
        else:
            if vocab != None and data != None:
                # Load vocabulary
                self.data = data
                self.vocab = vocab
            else:
                self.data  = []
                self.vocab = []

        self.vocab = list(set(self.vocab))
        self.vocab.sort()

        self.encoding_size = len(self.vocab)

        # Create dictionaries to support symbol to index conversion and vice-versa
        self.symbol_to_ix = { symb:i for i,symb in enumerate(self.vocab) }
        self.ix_to_symbol = { i:symb for i,symb in enumerate(self.vocab) }

    @abstractmethod
    def type(self):
        pass

    @abstractmethod
    def load(self, datapath):
        pass

    @abstractmethod
    def decode(self, datapoint):
        pass

    @abstractmethod
    def read(self, file):
        pass

    @abstractmethod
    def write(self, data, path):
        pass

    @abstractmethod
    def str2symbols(self, s):
        pass

    def slice(self, data, i, length):
        return [self.encode(ts) for ts in data[i:i+length]]

    def encode_sequence(self, sequence):
        return self.slice(sequence, 0, len(sequence))

    def encode(self, symb):
        if symb not in self.symbol_to_ix:
            return 0

        return self.symbol_to_ix[symb]
