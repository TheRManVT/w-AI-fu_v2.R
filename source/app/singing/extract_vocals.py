import sys
from audio_separator.separator import Separator

FILE_PATH = sys.argv[1]

separator = Separator()
separator.load_model("UVR-MDX-NET-Inst_HQ_3")

# Separate instrumental from voice
voice, inst = separator.separate(FILE_PATH)

separator.load_model("UVR_MDXNET_KARA")

# Separate main vocals to backing vocals
main, other = separator.separate(voice)