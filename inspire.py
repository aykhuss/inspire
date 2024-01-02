#!/usr/bin/env python

import argparse
import sys, os, shutil
import json
import urllib, urllib.request, urllib.parse
import configparser
from datetime import datetime
import re

from beaupy import confirm, prompt, select, select_multiple
from beaupy.spinners import *
from rich.console import Console
from rich.syntax import Syntax
from rich.progress import (Progress, BarColumn, TaskProgressColumn,
                           TimeRemainingColumn, TextColumn)

__version__ = '0.1'
__author__ = 'Alexander Huss'


def get_config() -> configparser.ConfigParser:
    #> local configuration file
    config_file = os.path.join(os.path.dirname(__file__), 'inspire.ini')
    #> default settings
    config_defaults = {
        'query': {
            'size': '10'
        },
        'local': {
            'max_num_authors': '5',
            'page_size': '5',
            'display': 'latex-eu',
            'bib_file': os.path.join(os.path.dirname(__file__),
                                     'bibliography', 'references.bib'),
            'pdf_dir': os.path.join(os.path.dirname(__file__),
                                    'bibliography', 'bibtex-pdfs')
        }
    }
    config = configparser.ConfigParser()
    config.read_dict(config_defaults)
    if os.path.exists(config_file):
        config.read(config_file)
    else:
        if confirm(
                'missing configuration file. create one now?\n[italic]{}[/italic]'
                .format(config_file),
                default_is_yes=True):
            default_size = prompt('default size of records to retrieve?',
                                  target_type=int,
                                  initial_value=config['query']['size'],
                                  validator=lambda count: count > 0)
            config.set(section='query', option='size', value=str(default_size))
            max_num_authors = prompt(
                'maximum number of authors to display?',
                target_type=int,
                initial_value=config['local']['max_num_authors'],
                validator=lambda count: count > 0)
            config.set(section='local', option='max_num_authors',
                       value=str(max_num_authors))
            default_bib = prompt('default bibliography file?',
                                 target_type=str,
                                 initial_value=config['local']['bib_file'])
            config.set(section='local', option='bib_file',
                       value=os.path.expanduser(default_bib))
            os.makedirs(os.path.dirname(config['local']['bib_file']),
                        exist_ok=True)
            with open(config['local']['bib_file'], 'w') as bib:
                bib.write("# created by {} on {} \n".format(
                    os.path.basename(__file__), datetime.now()))
            default_pdf_dir = prompt('default directory for PDF files?',
                                     target_type=str,
                                     initial_value=config['local']['pdf_dir'])
            config.set(section='local', option='pdf_dir',
                       value=os.path.expanduser(default_pdf_dir))
            os.makedirs(config['local']['pdf_dir'], exist_ok=True)
            with open(config_file, 'w') as cfg:
                config.write(cfg)
    return config


def get_records(query: str,
                sort: str = 'mostrecent',
                size: int = 1) -> tuple[list, int]:
    inspire_result = dict()
    inspire_query = 'https://inspirehep.net/api/literature'
    inspire_query += '?sort={}'.format(sort)
    inspire_query += '&size={:d}'.format(size)
    inspire_query += '&q=' + urllib.parse.quote(query)
    with urllib.request.urlopen(inspire_query) as req:
        inspire_result = json.load(req)
    return inspire_result["hits"]["hits"], inspire_result["hits"]["total"]


def make_label(record: dict, max_num_authors: int) -> str:
    label = ''
    label += '\t[underline]' + record['metadata']['texkeys'][0] + '[/underline]'
    if len(record['metadata']['texkeys']) > 1:
        for alt_texkey in record['metadata']['texkeys'][1:]:
            label += '[italic], [/italic]' + alt_texkey
    label += ' (' + record['metadata']['earliest_date'] + ')\n'
    author_list = ', '.join(
        map(lambda aut: aut['full_name'],
            record['metadata']['authors'][:max_num_authors]))
    if record['metadata']['author_count'] > max_num_authors:
        author_list += ' et al.'
    label += '\t[bold]' + author_list + '[/bold]' + '\n'
    label += '\t[italic]"' + record['metadata']['titles'][0][
        'title'] + '"[/italic]' + '\n'
    return label


def make_selection(records: list,
                   max_num_authors: int = 5,
                   page_size: int = 5) -> list:
    #> using records &
    #> preprocessor=lambda rec: make_label(rec, max_num_authors),
    #> becomes *really* slow for large sizes
    choices = [ make_label(rec, max_num_authors) for rec in records ]
    selected_indices = select_multiple(
        choices,
        tick_character='◦',
        pagination=True,
        page_size=page_size,
        return_indices=True,
        tick_style='blue',
        cursor_style='blue')
    return [records[i] for i in selected_indices]


def bib_get_texkeys(bib_file: str) -> list[str]:
    bib_texkeys = list()
    re_keys = re.compile(
        r'\s*@\w+\{\s*([a-zA-Z0-9_\-\.:]+)\s*,(?:[^\{\}]|\{[^\{\}]*\})*\}\s*',
        re.MULTILINE)
    with open(bib_file, 'r') as bib:
        bib_texkeys = re_keys.findall(bib.read())
    return bib_texkeys
def bib_append_entry(bib_file: str, bibtex: str) -> None:
    with open(bib_file, 'a') as bib:
        bib.write('\n' + bibtex)

#@todo: define Record class with these as methods?
def retrieve_link(record: dict, key: str = 'bibtex') -> str:
    return urllib.request.urlopen(
        record['links'][key]).read().decode('utf-8')
def download_pdf(record: dict, dest_file: str, exist_ok: bool = False) -> None:
    if os.path.exists(dest_file) and not exist_ok:
        raise FileExistsError('"{}" already exists'.format(dest_file))
    else:
        #> identifier: https://info.arxiv.org/help/arxiv_identifier_for_services.html
        #> alternatively could consider using the arix API? (seems overkill for now)
        if 'arxiv_eprints' in rec['metadata']:
            arxiv_id = record['metadata']['arxiv_eprints'][0]['value']
            #> old style has the category prefix (primary)
            if not re.match(r'\d+\.\d+', arxiv_id):
                arxiv_id = record['metadata']['arxiv_eprints'][0][
                    'categories'][0] + '/' + arxiv_id
            urllib.request.urlretrieve(
                'http://arxiv.org/pdf/' + arxiv_id + '.pdf', dest_file)
        else:
            raise ValueError('"{}" has no arXiv entry for PDF download'.format(
                record['metadata']['texkeys'][0]))


if __name__ == '__main__':
    console = Console()
    config = get_config()

    parser = argparse.ArgumentParser(prog='iNSPIRE',
                                     description='a simple CLI script to interact with iNSPIRE')
    parser.add_argument('query', nargs='*', help='the iNSPIRE query')
    parser.add_argument('-b', '--bib',
                        type=str,
                        nargs='?',
                        const=config['local']['bib_file'],
                        help='bibliography file to update')
    parser.add_argument('-u', '--update',
                        action='store_true',
                        help='update entire bibliography file')
    parser.add_argument('--sort',
                        default='mostrecent',
                        choices=['mostrecent', 'mostcited'],
                        help='the sorting order')
    parser.add_argument('-d', '--display',
                        nargs='?',
                        const=config['local']['display'],
                        choices=['bibtex', 'latex-eu', 'latex-us', 'json', 'cv', 'citations'],
                        help='display record')
    parser.add_argument('--size',
                        type=int,
                        default=int(config['query']['size']),
                        help='number of records to retrieve')
    parser.add_argument('--page-size',
                        type=int,
                        default=int(config['local']['page_size']),
                        help='number of records to show per page')
    args = parser.parse_args()
    # console.print(args)


    if args.update:
        if not args.bib:
            raise RuntimeError('update requires a bibliography file (-b [bib-file])')

        bib_bak = args.bib + '.bak'
        #@todo if backup exists ask user to restore it?
        shutil.copyfile(args.bib, bib_bak)
        bib_texkeys = bib_get_texkeys(args.bib)
        with open(args.bib, 'w') as bib:
            bib.write("# updated by {} on {} \n".format(
                os.path.basename(__file__), datetime.now()))
        with Progress(BarColumn(),
                      TaskProgressColumn(),
                      TimeRemainingColumn(),
                      TextColumn("[progress.description]{task.description}"),
                      transient=True) as progress:
            task = progress.add_task("updating", total=len(bib_texkeys))
            for texkey in bib_texkeys:
                records, total = get_records(texkey, size=1)
                records = list(
                    filter(lambda rec: 'texkeys' in rec['metadata'], records))
                records = list(
                    filter(lambda rec: texkey in rec['metadata']['texkeys'], records))
                if len(records) != 1:
                    raise ValueError('error with "{}": {}/{}'.format(
                        texkey, len(records), total))
                else:
                    bibtex = retrieve_link(records[0], 'bibtex')
                    bib_append_entry(args.bib, bibtex)
                progress.update(task, advance=1.0, description=texkey)
            os.remove(bib_bak)


    #> get records from inspirehep
    spinner = Spinner(DOTS, 'getting [blue]iNSPIRE[/blue]d...')
    spinner.start()
    records, total = get_records(' '.join(args.query), args.sort, args.size)
    spinner.stop()
    records = list(filter(lambda rec : 'texkeys' in rec['metadata'], records))
    console.print("total: {}; size: {}".format(total, len(records)))

    if total > 1:
        records = make_selection(records, int(config['local']['max_num_authors']),
                                 int(config['local']['page_size']))

    #> all texkeys in the database
    if args.bib:
        bib_texkeys = bib_get_texkeys(args.bib)
    else:
        bib_texkeys = []

    #> get bibtex entries
    for rec in records:
        texkey = rec['metadata']['texkeys'][0]
        if not args.bib or args.display:
            key = args.display if args.display else config['local']['display']
            if key in ['latex-eu', 'latex-us']:
                lexer = 'tex'
            elif key in ['bibtex']:
                lexer = 'bibtex'
            elif key in ['cv']:
                lexer = 'html'
            elif key in ['json', 'citations']:
                lexer = 'json'
            else:
                lexer = 'text'
            spinner = Spinner(DOTS, "fetching {} for {}...".format(key,texkey))
            spinner.start()
            syntax = Syntax('\n' + retrieve_link(rec, key), lexer=lexer, word_wrap=True)
            spinner.stop()
            console.print(syntax)
        else:
            spinner = Spinner(DOTS, "fetching BibTeX for {}...".format(texkey))
            spinner.start()
            bibtex = retrieve_link(rec,'bibtex')
            spinner.stop()

            if texkey in bib_texkeys :
                console.print('entry "{}" found in database'.format(texkey))
            else:
                bib_append_entry(args.bib,bibtex)

            #> get the PDF file and save
            pdf_file = os.path.join(config['local']['pdf_dir'] , texkey + '.pdf')
            spinner = Spinner(DOTS, 'downloading PDF for "{}"...'.format(texkey))
            spinner.start()
            try:
                download_pdf(rec, pdf_file)
            except FileExistsError as e:
                spinner.stop()
                console.print(str(e))
                if confirm( 're download?'):
                    spinner.start()
                    download_pdf(rec, pdf_file, exist_ok=True)
            except Exception as e:
                console.print(str(e))
            spinner.stop()
