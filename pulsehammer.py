"""Thin entry point that delegates to the pulsehammer package."""
from pulsehammer.cli import build_parser, run


def main():
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
