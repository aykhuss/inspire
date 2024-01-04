# inspire
> A simple python CLI script to query inspirehep.net and populate bibliography databases.

An [iNSPIRE](https://inspirehep.net) CLI script using its [REST API](https://github.com/inspirehep/rest-api-doc).

## Requirements
This script requires `python 3.9` or above.
The requirements can be installed via
```
python -m pip install -r requirements.txt
```
or by manually inspect the `requirements.txt` file.


## Usage

### Retrieve and display record
Simply pass an iNSPIRE [query](https://help.inspirehep.net/knowledge-base/inspire-paper-search/) to the command line and use the `--display` (`-d`) option to control the output:

![display](./examples/display.gif)

### Select entries
When there are multiple matches, `--size` controls the number of records to retrieve and `--sort` the sorting order. The wanted entries can be easily selected from the menu:

![select](./examples/select.gif)

### Populate bibliography
The selected entries can be added to an existing bibliography by specifying the file with `--bib` (`-b`). Omitting the file name will use the default BibTeX file specified in the configuration:

![bib](./examples/bib.gif)

### Update entries
We can also update all records of an existing BibTeX file by adding the `--update` (`-u`) option:

![update](./examples/update.gif)

### Help
Check out help dialogue for usage
```
inspire.py -h 
```
