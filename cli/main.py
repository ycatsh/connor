import argparse

from cli.commands import ConnorCLI


def main():
    parser = argparse.ArgumentParser(prog='Connor', description='Connor: Fast and local NLP file organizer')
    subparsers = parser.add_subparsers(dest='command')

    # Subparser for updating settings
    settings_parser = subparsers.add_parser('settings', help='Update the settings for the organizer')
    settings_parser.add_argument('--folder-name-length', type=int, help='Max folder name length (default: 2)')
    settings_parser.add_argument('--reading-word-limit', type=int, help='Word limit for reading files (default: 100)')
    settings_parser.add_argument('--similarity-threshold', type=int, help='Similarity threshold percentage (default: 50)')

    # Subparser for running the organization
    run_parser = subparsers.add_parser('run', help='Run the folder organization process')
    run_parser.add_argument('--path', type=str, required=True, help='Path to the folder to organize')

    args = parser.parse_args()
    cli_tool = ConnorCLI()

    if args.command == 'settings':
        if not (args.folder_name_length or args.reading_word_limit or args.similarity_threshold):
            settings_parser.print_help()
        else:
            cli_tool.update_settings(folder_name_length=args.folder_name_length, reading_word_limit=args.reading_word_limit, similarity_threshold=args.similarity_threshold)
    elif args.command == 'run':
        cli_tool.organize_folder(args.path)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()