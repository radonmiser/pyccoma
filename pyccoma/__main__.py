#!/usr/bin/env python

import argparse

import re
import os
import sys
import logging
from getpass import getpass
from itertools import chain
from typing import Optional, Union, Tuple, List

from pyccoma.pyccoma import Scraper
from pyccoma.exceptions import PyccomaError
from pyccoma.logger import setup_logging, levels
from pyccoma.helpers import create_tags, valid_url
from pyccoma.urls import history_url, bookmark_url, purchase_url

log = logging.getLogger(__name__)
pyccoma = Scraper()

def main() -> None:
    try:
        setup_logging()
        parser = construct_parser()
        args = parser.parse_args()
        url = args.url

        if args.format:
            pyccoma.format = args.format

        if args.etype:
            pyccoma.manga = args.etype[0]
            pyccoma.smartoon = args.etype[1]
            pyccoma.novel = args.etype[2]

        if args.retry_count:
            pyccoma.retry_count = args.retry_count

        if args.retry_interval:
            pyccoma.retry_interval = args.retry_interval

        if args.omit_author:
            pyccoma.omit_author = args.omit_author

        if args.loglevel:
            logging.getLogger().setLevel(args.loglevel)

        if not args.range and not 'viewer' in args.url and args.filter == 'custom':
            raise PyccomaError("Use --filter custom along with --range.")

        elif (args.range and not args.filter) or (args.range and args.filter in ('min', 'max', 'all')):
            log.warning("Overriding --filter={0} to parse custom.".format(args.filter))
            args.filter = 'custom'

        password = ""

        if args.email:
            if not password:
                password = getpass()

            pyccoma.login(args.email, password)

        if args.url and args.filter:
            if args.url[0] in ('history', 'bookmark', 'purchase'):
                if args.url[0] in history_url:
                    url = pyccoma.get_history().values()
                    log.info("Parsing ({0}) items from your history library.".format(len(url)))

                elif args.url[0] in bookmark_url:
                    url = pyccoma.get_bookmark().values()
                    log.info("Parsing ({0}) items from your bookmark library.".format(len(url)))

                elif args.url[0] in purchase_url:
                    url = pyccoma.get_purchase().values()
                    log.info("Parsing ({0}) items from your purchase library.".format(len(url)))

            elif valid_url(args.url[0], level=3):
                raise PyccomaError(
                    "There is nothing to aggregate. You should only use "
                    "--filter on a product page or your library."
                )

        if any(map(valid_url, args.url)):
            if not os.path.exists(args.output) and not args.output:
                log.warning(
                    "No path found, creating an extract folder inside "
                    "the current working directory: {0}".format(os.getcwd())
                )
            fetch(
                url,
                args.filter,
                args.range,
                args.include,
                args.exclude,
                args.output
            )
        else:
            raise ValueError("Invalid url.")

    except Exception as error:
        parser.error(error)

def construct_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyccoma",
        description=" Scrape and download from Piccoma. ",
        epilog="""
        Report bugs and make feature requests at https://github.com/catsital/pyccoma/issues
        """,
        add_help=False,
    )

    required = parser.add_argument_group("Required options")
    required.add_argument(
        "url",
        nargs="*",
        help="""
        Link to an episode or product. If logged in, use: history, bookmark, or purchase
        as shorthand to your library.
        """
    )

    optional = parser.add_argument_group("General options")
    optional.add_argument(
        "-o",
        "--output",
        type=str,
        default="extract",
        help="Path to save downloaded images."
    )
    optional.add_argument(
        "-f",
        "--format",
        type=str,
        default="png",
        help="Image format: png, jpeg, jpg, bmp (Default: png)"
    )
    optional.add_argument(
        "--retry-count",
        type=int,
        metavar=("COUNT"),
        default=3,
        help="Number of download retry attempts when error occurred. (Default: 3)"
    )
    optional.add_argument(
        "--retry-interval",
        type=int,
        metavar=("SECONDS"),
        default=1,
        help="Delay between each retry attempt. (Default: 1)"
    )
    optional.add_argument(
        "--omit-author",
        dest="omit_author",
        action="store_true",
        default=False,
        help="Omit author(s) in title naming scheme."
    )

    user = parser.add_argument_group("Login options")
    user.add_argument(
        "--email",
        type=str,
        help="Account email address."
    )

    filter = parser.add_argument_group("Filter options")
    filter.add_argument(
        "--etype",
        type=str,
        nargs=3,
        metavar=("MANGA", "SMARTOON", "NOVEL"),
        default=["volume", "episode", "episode"],
        help="""
        Preferred episode type to scrape manga, smartoon and novel when aggregating
        your library. (Default: manga=volume smartoon=episode novel=episode)
        """
    )
    filter.add_argument(
        "--filter",
        type=str,
        help="""
        Filter to use when aggregating products or scraping library. Can be either:
        min, max, all, or custom with --range.
        """
    )
    filter.add_argument(
        "--range",
        type=int,
        nargs=2,
        metavar=("START", "END"),
        help="Range to use when scraping episodes or volumes."
    )
    filter.add_argument(
        "--include",
        type=include,
        default="episode",
        help="""
        Arguments to include when parsing your library: is_purchased, is_free,
        is_already_read, is_limited_read, is_limited_free
        """
    )
    filter.add_argument(
        "--exclude",
        type=exclude,
        default="",
        help="""
        Arguments to exclude when parsing your library: is_purchased, is_free,
        is_already_read, is_limited_read, is_limited_free
        """
    )

    logger = parser.add_argument_group("Logging options")
    logger.add_argument(
        "-l", "--loglevel",
        metavar="LEVEL",
        choices=levels,
        default="info",
        help="""
        Set the log message threshold. Valid levels are: debug, info, warning,
        error, none (Default: info)
        """
    )

    info = parser.add_argument_group("Info")
    info.add_argument("-h", "--help", action="help", help="Show this help message and exit."),
    info.add_argument("-v", "--version", action="version", help="Show program version.", version="%(prog)s 0.4.0")

    return parser

def include(value: str) -> str:
    try:
        include = create_tags(value).replace("&", " and ").replace("|", " or ")
        return include
    except Exception:
        raise argparse.ArgumentTypeError('Specify type in this format: "is_free|is_already_read"')

def exclude(value: str) -> str:
    try:
        exclude = create_tags(value).replace("&", " and ").replace("|", " or ")
        return exclude
    except Exception:
        raise argparse.ArgumentTypeError('Specify type in this format: "is_free&is_already_read"')

def fetch(
    url: List[str],
    mode: Optional[str] = None,
    range: Optional[Tuple[int, int]] = None,
    include: Optional[str] = None,
    exclude: Optional[str] = None,
    output: Optional[str] = None
) -> None:
    if mode:
        try:
            if not range:
                range = (0, 0)

            filter = {
                'min': '[episode[0] for episode in episodes if episode]',
                'max': '[episode[-1] for episode in episodes if episode]',
                'all': 'list(chain.from_iterable(episodes))',
                'custom': f"list(chain.from_iterable(episodes))[{range[0]}:{range[1]}]",
            }

            exclude = " {0}not ({1})".format("and " if include else "", exclude)
            flags = (include) + (exclude)

            episodes = []

            for title in url:
                episodes.append(
                    product := [episode['url'] for episode in pyccoma.get_list(title).values() if eval(flags)]
                )

            episodes = eval(filter[mode])
            episodes_total = len(episodes)
            log.info(f"Fetching ({episodes_total}) episodes.")

            for index, episode in enumerate(episodes):
                log.info(f"Fetching ({index+1}/{episodes_total})")
                pyccoma.fetch(episode, output)

        except Exception as error:
            raise PyccomaError(error)

    else:
        for index, link in enumerate(url):
            if valid_url(url=link, level=3):
                log.info(f"Fetching ({index+1}/{len(url)})")
                pyccoma.fetch(link, output)
            elif valid_url(url=link, level=0):
                raise PyccomaError("Use --filter to aggregate episodes in product pages.")
            else:
                raise ValueError("Invalid url.")

if __name__ == "__main__":
    main()
