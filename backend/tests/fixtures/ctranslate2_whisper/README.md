Numeric log-mel fixtures generated once from the installed faster-whisper 1.2.1
`feature_extractor.py` via `importlib.util.spec_from_file_location`, without importing
the faster-whisper package. NumPy 2.5.2, default extractor parameters, feature sizes
80 and 128. Each input has 800 float32 samples at 16 kHz:

- silence: all zeros;
- tone: `0.2 * sin(2*pi*440*arange(800)/16000)` converted to float32;
- impulse: zeros with sample 400 equal to one.

The `.npy` files contain the complete reference outputs, not selected samples.
Tests reconstruct these synthetic inputs and compare every output value. No media
or transcript data is included. Reference licensing: MIT, copyright 2023 SYSTRAN.
