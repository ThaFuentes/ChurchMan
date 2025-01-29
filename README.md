# Development Setup
```bash
python3 -m venv --prompt="churchman" env
source env/bin/activate
pip install -r requirements.txt
```
Now your operational dependencies are met.
The database is created on first executing main.py.
```bash
python main.py
```
You can kill that with Ctrl+C.

## Recommended dependencies for local development environment
```bash
pip install gunicorn # A WSGI server
pip install flake8   # A linter
```
If you install these optional dependencies, you can run them from
the command line. flake8 can also be integrated with your text editor,
to lint files as you write them. `flake8` will give output showing where the
code deviates from the PEP8 standard for python formatting.

Gunicorn can be run like so:
```bash
gunicorn -w 4 -b '0.0.0.0:8080' 'wsgi:application'
```
The `-w 4` flag makes gunicorn serve the application with
four workers, for up to four concurrent requests.
The `-b '0.0.0.0:8080'` will bind to that network interface.
