# 📦 micrOS Application: sound\_event

Trainable sound-event recognition for micrOS using an I2S microphone. It captures audio events, classifies them with instance-based learning, stores labeled examples in a dataset, and supports optional SD card storage.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/sound_event"
```

```bash
pacman upgrade "sound_event"
pacman uninstall "sound_event"
```

## Device Layout

- Package files: `/lib/sound_event`
- Load module: `/modules/LM_sound_event.py`

## Usage

```commandline
sound_event load
sound_event load dataset='sound_events.pds' capture_duration_ms=192 max_event_duration_ms=3000 frame_size_ms=80 pause_duration_ms=500 event_buffer_length=1 sd_storage=False
sound_event classify_last_event
sound_event record_last_event label='finger_snaps'
sound_event get_classes
sound_event get_events
sound_event get_performance
sound_event autolearn enabled=True
sound_event remove_last_instance
sound_event remove_instance_by_idx idx=0
sound_event remove_class class_name='finger_snaps'
sound_event relabel_class old_label='finger_snaps' new_label='snap'
sound_event remove_classes
sound_event pinmap
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#sound_event)

## Dependency

Dependencies are auto installed by `mip` based on `package.json`

### built-ins

```text
LM_i2s_mic
```
