import argparse

from gui.main import main as gui_main
from cli.main import main as cli_main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Connor', description="Connor DEV: Run the application in GUI or CLI mode.")
    parser.add_argument('--cli', action='store_true', help='Run the application in CLI mode.')
    parser.add_argument('--gui', action='store_true', help='Run the application in GUI mode.')
    args = parser.parse_args()

    if args.cli:
        cli_main()
    elif args.gui:
        gui_main()
    else:
        print("No mode specified. Use --cli for CLI mode or --gui for GUI mode.")
