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

#@todo check that it's python3? and terminate gracefully otherwise?

console = Console()

#> read in the configuration, otherwise create it
config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__) , 'inspire.ini')
if os.path.exists(config_file):
    config.read(config_file)
else:
    if confirm("missing configuration file. create one now?", default_is_yes=True):
        config.add_section('query')
        default_size = prompt('Default result length?',
                              target_type=int, initial_value='10',
                              validator=lambda count: count > 0)
        config.set(section='query', option='size', value=str(default_size))
        config.add_section('local')
        max_num_authors = prompt('maximum number of authors to display?',
                              target_type=int, initial_value='5',
                              validator=lambda count: count > 0)
        config.set(section='local', option='max_num_authors', value=str(max_num_authors))
        default_bib = prompt('Default bibliography file?', target_type=str)
        # , validator=lambda bib_file: os.path.isfile(bib_file))
        config.set(section='local',
                   option='bib_file',
                   value=os.path.expanduser(default_bib))
        os.makedirs(os.path.dirname(config['local']['bib_file']), exist_ok=True)
        with open(config['local']['bib_file'], 'w') as bib:
            bib.write("# created by {} on {} \n".format(__file__,datetime.now()))
        default_pdf_dir = prompt('Default PDF directory?', target_type=str)
        # , validator=lambda pdf_dir: os.path.isdir(pdf_dir))
        config.set(section='local',
                   option='pdf_dir',
                   value=os.path.expanduser(default_pdf_dir))
        os.makedirs(config['local']['pdf_dir'], exist_ok=True)
        with open(config_file, 'w') as cfg:
            config.write(cfg)

parser = argparse.ArgumentParser(prog='inspire',
                                 description='an amazing inspire CLI script')
#> no separate query argument
#> for convenience we'll take the remainder to be the query (see below)
#parser.add_argument("-q", "--query", type=str, required=True)
#> we do literature search only for now...
parser.add_argument('--sort',
                    type=str,
                    default='mostrecent',
                    const='mostrecent',
                    nargs='?',
                    choices=['mostrecent', 'mostcited'],
                    help='the sorting order')
parser.add_argument('--size',
                    type=int,
                    default=int(config['query']['size']),
                    help='number of records to display')
parser.add_argument('--downlaod',
                    type=bool,
                    help='try to downlaod the PDF file')
parser.add_argument('query', nargs='*',
                    help='the inspirehep query')  # all the left-overs
args = parser.parse_args()
# console.print(args)

#> get records from inspirehep
spinner = Spinner(DOTS, "getting [blue]iNSPIRE[/blue]d...")
spinner.start()
records = dict()
query = "https://inspirehep.net/api/literature"
query += '?sort={}'.format(args.sort)
query += '&size={:d}'.format(args.size)
query += '&q=' + urllib.parse.quote(" ".join(args.query))
with urllib.request.urlopen(query) as req:
    records = json.load(req)
spinner.stop()
# console.print(json.dumps(records))

if len(records) > 0:
    console.print("total: {}; size: {}".format(records["hits"]["total"],
                                               len(records["hits"]["hits"])))

# #> inspect the entry
# for hit in records["hits"]["hits"]:
#     console.print(hit.keys())
#     console.print(hit['links'])
#     console.print(hit['metadata'].keys())
#     #console.print(hit['metadata']['arxiv_eprints'])
#     console.print(hit['metadata']['earliest_date'])
#     console.print(hit['metadata']['authors'])
#     console.print( ", ".join(map(lambda aut : aut['last_name'], hit['metadata']['authors'][:10])) + (" et al." if hit['metadata']['author_count'] > 10 else "") )
# #sys.exit(0)
def make_label(hit: dict, max_num_authors: int) -> str:
    label = ''
    label += '\t[underline]' + hit['metadata']['texkeys'][0] + '[/underline]'
    if len(hit['metadata']['texkeys']) > 1:
        for alt_texkey in hit['metadata']['texkeys'][1:]:
            label += '[italic], [/italic]' + alt_texkey
    label += ' (' + hit['metadata']['earliest_date'] + ')\n'
    author_list = ', '.join(
        map(lambda aut: aut['full_name'],
            hit['metadata']['authors'][:max_num_authors]))
    if hit['metadata']['author_count'] > max_num_authors:
        author_list += ' et al.'
    label += '\t[bold]' + author_list + '[/bold]' + '\n'
    label += '\t[italic]"' + hit['metadata']['titles'][0][
        'title'] + '"[/italic]' + '\n'
    return label
choices = [
    make_label(hit, int(config['local']['max_num_authors']))
    for hit in records["hits"]["hits"]
]

selected_indices = select_multiple(choices,
                        tick_character='◦',
                        pagination=True,
                        page_size=5,
                        return_indices=True,tick_style='blue',cursor_style='blue')

#> all texkeys in the database
bib_texkeys = list()
re_keys = re.compile(r'@\w+\{\s*([a-zA-Z0-9_\-\.:]+)\s*,(?:[^\{\}]|\{[^\{\}]*\})*\}',re.MULTILINE)
with open(config['local']['bib_file'],'r') as bib:
    bib_texkeys = re_keys.findall(bib.read())

do_update = True

#> get bibtex entries and save to file
for idx in selected_indices:
    texkey = records["hits"]["hits"][idx]['metadata']['texkeys'][0]
    spinner = Spinner(DOTS, "fetching BibTeX for {}...".format(texkey))
    spinner.start()
    bibtex = urllib.request.urlopen(records["hits"]["hits"][idx]['links']['bibtex']).read().decode('utf-8')
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
        if 'arxiv_eprints' in records["hits"]["hits"][idx]['metadata']:
            arxiv_id = records["hits"]["hits"][idx]['metadata']['arxiv_eprints'][0]['value']
            #> old style has the category prefix (primary)
            if not re.match(r'\d+\.\d+', arxiv_id):
                arxiv_id = records['hits']['hits'][idx]['metadata']['arxiv_eprints'][0]['categories'][0] + '/' + arxiv_id
            spinner = Spinner(DOTS, 'downloading PDF for "{}" from arXiv:{}...'.format(texkey,arxiv_id))
            spinner.start()
            urllib.request.urlretrieve('http://arxiv.org/pdf/' + arxiv_id + '.pdf', pdf_file)
            spinner.stop()
        else:
            console.print('"{}" has no arXiv entry for PDF download'.format(texkey))


sys.exit(0)


