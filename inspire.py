#!/usr/bin/env python

import argparse
import time
import sys
import os
import json
import urllib, urllib.request, urllib.parse
import configparser
from datetime import datetime
import re

from beaupy import confirm, prompt, select, select_multiple
from beaupy.spinners import *
from rich.console import Console

__version__ = '0.1'
__author__ = 'Alexander Huss'


console = Console()


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
config = get_config()

parser = argparse.ArgumentParser(prog='iNSPIRE',
                                 description='an amazing inspire CLI script')
parser.add_argument('query', nargs='*', help='the inspirehep query')
parser.add_argument('-b',
                    '--bib',
                    type=str,
                    nargs='?',
                    const='default.bib',
                    help='bibliography file to update')
parser.add_argument('-u',
                    '--update',
                    action='store_true',
                    help='update entire bibliography file')
parser.add_argument('--sort',
                    default='mostrecent',
                    choices=['mostrecent', 'mostcited'],
                    help='the sorting order')
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

def get_records(query: str,
                sort: str = 'mostrecent',
                size: int = 1) -> tuple[list, int]:
    inspire_result = dict()
    inspire_query = 'https://inspirehep.net/api/literature'
    inspire_query += '?sort={}'.format(sort)
    inspire_query += '&size={:d}'.format(size)
    inspire_query += '&q=' + urllib.parse.quote(query)
    console.print(inspire_query)
    with urllib.request.urlopen(inspire_query) as req:
        inspire_result = json.load(req)
    return inspire_result["hits"]["hits"], inspire_result["hits"]["total"]


#> get records from inspirehep
spinner = Spinner(DOTS, 'getting [blue]iNSPIRE[/blue]d...')
spinner.start()
records, total = get_records(' '.join(args.query), args.sort, args.size)
spinner.stop()
console.print("total: {}; size: {}".format(total, len(records)))



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
    selected_indices = select_multiple(
        records,
        preprocessor=lambda rec: make_label(rec, max_num_authors),
        tick_character='◦',
        pagination=True,
        page_size=page_size,
        return_indices=True,
        tick_style='blue',
        cursor_style='blue')
    return [records[i] for i in selected_indices]

records = make_selection(records, int(config['local']['max_num_authors']),
                         int(config['local']['page_size']))

def get_bib_texkeys(bib_file: str) -> list[str]:
    bib_texkeys = list()
    re_keys = re.compile(
        r'@\w+\{\s*([a-zA-Z0-9_\-\.:]+)\s*,(?:[^\{\}]|\{[^\{\}]*\})*\}',
        re.MULTILINE)
    with open(bib_file, 'r') as bib:
        bib_texkeys = re_keys.findall(bib.read())
    return bib_texkeys

#> all texkeys in the database
bib_texkeys = get_bib_texkeys(config['local']['bib_file'])

do_update = True

#> get bibtex entries and save to file
for rec in records:
    texkey = rec['metadata']['texkeys'][0]
    spinner = Spinner(DOTS, "fetching BibTeX for {}...".format(texkey))
    spinner.start()
    bibtex = urllib.request.urlopen(rec['links']['bibtex']).read().decode('utf-8')
    spinner.stop()
    console.print(bibtex)
    # re_key = re.compile(r'@\w+\{\s*'+texkey+r'\s*,(?:[^\{\}]|\{[^\{\}]*\})*\}',re.MULTILINE)
    # with open(config['local']['bib_file'],'r') as bib:
    #     res = re_key.findall(bib.read())
    #     console.print("FINDALL")
    #     console.print(res)
    # res = re_key.findall(bibtex)
    # console.print("FINDSELF")
    # console.print(res)
    #> check database if already there
    # with open(config['local']['bib_file'],'r+') as bib:
    #     if bib.read().count(texkey) == 0:
    #         bib.write('\n' + bibtex + '\n')
    #     else:
    #         console.print('entry "{}" already in database'.format(texkey))
    #> append to bib file
    if texkey in bib_texkeys :
        console.print('entry "{}" found in database'.format(texkey))
        if do_update:
            print("time for an update!")
            re_key = re.compile(r'@\w+\{\s*'+texkey+r'\s*,(?:[^\{\}]|\{[^\{\}]*\})*\}',re.MULTILINE)
        #@todo:  allow update option?
        #continue
    else:
        with open(config['local']['bib_file'],'a') as bib:
            bib.write('\n' + bibtex)

    #> get the PDF file and save
    pdf_file = os.path.join(config['local']['pdf_dir'] , texkey + '.pdf')
    if os.path.exists(pdf_file):
        console.print('already have PDF for record "{}"'.format(texkey))
        #@todo check timestamp and update?
        pass
    else:
        #> identifier: https://info.arxiv.org/help/arxiv_identifier_for_services.html
        #> alternatively could consider using the arix API? (seems overkill for now)
        #> has arxiv entry?
        if 'arxiv_eprints' in rec['metadata']:
            arxiv_id = rec['metadata']['arxiv_eprints'][0]['value']
            #> old style has the category prefix (primary)
            if not re.match(r'\d+\.\d+', arxiv_id):
                arxiv_id = rec['metadata']['arxiv_eprints'][0]['categories'][0] + '/' + arxiv_id
            spinner = Spinner(DOTS, 'downloading PDF for "{}" from arXiv:{}...'.format(texkey,arxiv_id))
            spinner.start()
            urllib.request.urlretrieve('http://arxiv.org/pdf/' + arxiv_id + '.pdf', pdf_file)
            spinner.stop()
        else:
            console.print('"{}" has no arXiv entry for PDF download'.format(texkey))


sys.exit(0)


