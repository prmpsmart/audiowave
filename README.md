
# AudioWave

A Python, Qt library that showcases playing of Audio wave and visualizing of Audio waveforms. Audio waveform or Audiogram widget.

## Classes

1. [*audiowave.py*](audiowave/audiowave.py)

    . **AudioWave** - splitting audio wave data into array of integers and into each channels

    . **SamplingMethod(enum.Enum)**
    
    . **AudioWaveChannel** - scaling and sampling of a channel of the audio wave data

2. [*audiowavelive.py*](audiowave/audiowavelive.py)

    . **LiveAudioWave** - base class for recording and playiing of audiowave data.

    . **AudioWaveRecorder(LiveAudioWave)**

    . **AudioWavePlayer(LiveAudioWave)**

    . **TimedLiveAudioWave** - recoring or playing of audiowave data and emitting a signal with the ongoing seconds of operation.

    . **TimedLiveAudioWavePlayer(TimedLiveAudioWave)**

    . **TimedLiveAudioWaveRecorder(TimedLiveAudioWave)**


3. [*audiowaveform.py*](audiowave/audiowaveform.py)

    . **AudioWaveFormGravity(enum.Enum)**

    . **AudioWaveFormOptions** - the ui properties of the painted waveforms for each channel

    . **AudioWaveFormChannel(AudioWaveChannel)** - channel data holder for the waveform painting.

    . **AudioWaveForm(QFrame)**

    . **LiveAudioWaveFormChannel(AudioWaveChannel, QObject)** - channel data holder for the live waveform painting.

    . **LiveAudioWaveForm(AudioWaveForm)** - waveforms being updated at the data increases

    . **FixedLiveAudioWaveForm(AudioWaveForm)**

4. [*audiolivewaveform.py*](audiowave\audiolivewaveform.py)

    . **TimedLiveAudioWaveForm(TimedLiveAudioWave)**
    
    . **PlayingAudioWaveForm(LiveAudioWaveForm, TimedLiveAudioWaveForm)**
    
    . **RecordingAudioWaveForm(TimedLiveAudioWaveForm, LiveAudioWaveForm)**
    
    . **PlayingFixedAudioWaveForm(TimedLiveAudioWaveForm, FixedLiveAudioWaveForm)**

## Example
run the [audiowave_examples.py](tests\audiowave_examples.py) and check out the possibilities.

![audiowave_examples.png](tests\test.PNG)


## DOCUMENTATION OF THE LIBRARY IS UPCOMING.
