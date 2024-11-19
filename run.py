import argparse

from gui import main as gui_main
from cli import main as cli_main


def main():
    parser = argparse.ArgumentParser(prog='Connor', description='Connor: Fast and local NLP file organizer')
    parser.add_argument('--gui', action='store_true', help='Run the application in GUI mode.')
    subparsers = parser.add_subparsers(dest='command')

    # Subparser for updating settings
    settings_parser = subparsers.add_parser('settings', help='Update the settings for the organizer')
    settings_parser.add_argument( '-f', '--folder-word-limit', type=int, 
                                 help='Specify the maximum number of words allowed in the created folder names')
    settings_parser.add_argument( '-r', '--reading-limit',type=int, 
                                 help='Set a limit on the number of words to read from the file content')
    settings_parser.add_argument('-t', '--similarity-threshold', type=int, 
                                 help='Change the similarity threshold for a custom threshold percentage for grouping similar files')
    settings_parser.add_argument('--show', action='store_true', help='Show current settings')

    # Subparser for running the organization
    run_parser = subparsers.add_parser('run', help='Run the folder organization process')
    run_parser.add_argument('path', type=str, help='Path to the folder to organize')

    args = parser.parse_args()
    cli_tool = cli_main()

    # GUI
    if args.gui:
        gui_main()
    else:
        # Organize
        if args.command == 'run':
            cli_tool.organize_folder(args.path)
        # Settings
        elif args.command == 'settings':
            if args.show:
                cli_tool.show_settings()
            elif (args.folder_word_limit or args.reading_limit or args.similarity_threshold):
                cli_tool.update_settings(
                    folder_name_length=args.folder_word_limit, 
                    reading_word_limit=args.reading_limit, 
                    similarity_threshold=args.similarity_threshold
                )
            else:
                settings_parser.print_help()
        # Help
        else:
            parser.print_help()

if __name__ == '__main__':
    main()