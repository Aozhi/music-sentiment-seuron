# External imports
import os

# Internal imports
from ..encoder import Encoder

class EncoderText(Encoder):
    def load(self, datapath):
        encoded_text = []

        vocab = set()

        # Read every file in the given directory
        data_size = 0
        for file in os.listdir(datapath):
            textpath = os.path.join(datapath, file)

            # Check if it is not a directory and if it has either .midi or .mid extentions
            if os.path.isfile(textpath) and (textpath[-4:] == ".txt"):
                txt = open(textpath, "r")
                txt_content = txt.read()
                txt_name = textpath.split("/")[-1]

                vocab = vocab | set(txt_content)
                encoded_text.append((textpath, txt_name))
                txt.close()

        return encoded_text, vocab

    def type(self):
        return "txt"

    def str2symbols(self, s):
        return s

    def decode(self, ixs):
        return ''.join(self.ix_to_symbol[ix] for ix in ixs)

    def read(self, file):
        fp = open(file, "r")
        content = fp.read()
        fp.close()
        return content

    def write(self, text, path):
        f = open(path + ".txt", "w")
        f.write(text)
        f.close()
