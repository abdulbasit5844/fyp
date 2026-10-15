"""python -m dms_edge [--source 0|picamera|video.mp4] [--show] [--no-verify]"""
import argparse
import logging

from .settings import DeviceSettings


def main():
    s = DeviceSettings()
    ap = argparse.ArgumentParser(prog="dms_edge", description="Driver monitoring edge pipeline")
    ap.add_argument("--source", default=s.source, help="auto | picamera | camera index | video file / URL")
    ap.add_argument("--device-id", default=s.device_id)
    ap.add_argument("--clips-dir", default=str(s.clips_dir))
    ap.add_argument("--show", action="store_true", help="show an annotated preview window (press 'a' to ack)")
    ap.add_argument("--no-verify", action="store_true", help="skip driver identity verification")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    s.source, s.device_id = args.source, args.device_id
    s.clips_dir = type(s.clips_dir)(args.clips_dir)

    from .pipeline import Pipeline  # heavy imports after arg parsing

    Pipeline(s, show=args.show, verify=not args.no_verify).run()


if __name__ == "__main__":
    main()
