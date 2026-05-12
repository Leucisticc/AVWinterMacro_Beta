import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Tools import avMethods as avM


WAVE_REGION = (595, 158, 23, 24)
DEBUG_WAVE = False
READ_DELAY_SECONDS = 0.25
PRINT_ONLY_ON_CHANGE = False


def main():
    last_wave = None

    print("Wave reader running.")
    print(f"Region: {WAVE_REGION}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            wave = avM.get_wave(region=WAVE_REGION, debug=DEBUG_WAVE)

            if not PRINT_ONLY_ON_CHANGE or wave != last_wave:
                print(f"wave: {wave}")

            last_wave = wave
            time.sleep(READ_DELAY_SECONDS)
    except KeyboardInterrupt:
        print("\nWave reader stopped.")


if __name__ == "__main__":
    main()
