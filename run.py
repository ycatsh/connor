import argparse

from gui.main import main as gui_main
from cli.main import main as cli_main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Connor', description="Connor DEV: Run the application in GUI or CLI mode.")
    parser.add_argument('--gui', action='store_true', help='Run the application in GUI mode.')
    args, unknown = parser.parse_known_args()

    if args.gui:
        gui_main()
    else:
        cli_main()