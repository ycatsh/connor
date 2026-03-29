import argparse
from connor.cli import ConnorCLI


def main():
    parser = argparse.ArgumentParser(
        description="Connor: Fast file classifier and organizer using NLP"
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    settings_parser = subparsers.add_parser('settings', help="View or update settings.")
    settings_parser.add_argument('-f', '--folder_word_limit', type=int, help="Set folder word limit.")
    settings_parser.add_argument('-r', '--reading_word_limit', type=int, help="Set reading word limit.")

    organize_parser = subparsers.add_parser('run', help="Organize a folder.")
    organize_parser.add_argument('path', type=str, help="Path to the folder to organize.")

    args = parser.parse_args()
    cli = ConnorCLI()

    if args.command == 'settings':
        if args.folder_word_limit is not None or args.reading_word_limit is not None:
            cli.update_settings(
                folder_word_limit=args.folder_word_limit,
                reading_word_limit=args.reading_word_limit,
            )
        else:
            cli.show_settings()

    elif args.command == 'run':
        cli.organize_folder(args.path)


if __name__ == "__main__":
    main()
