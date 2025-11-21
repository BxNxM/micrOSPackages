from Common import syslog


def setup(control, control_clb, haptic):
    # Trackball setup
    if control is not None and control.strip() == "trackball":
        try:
            from LM_trackball import subscribe_event
            subscribe_event(control_clb)
        except Exception as e:
            syslog(f"[ERR] oledui trackball: {e}")
    # Haptic setup
    if haptic:
        try:
            from LM_haptic import tap
            return tap
        except Exception as e:
            syslog(f"[ERR] oledui haptic: {e}")
    return None