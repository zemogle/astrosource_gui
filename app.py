import datetime
import os
from time import sleep
from flask import Flask, render_template, Response, request, url_for, flash, redirect
from loguru import logger
from pathlib import Path
import threading
from numpy import array

from astrosource.utils import convert_coords, AstrosourceException, setup_logger
from astrosource.astrosource import TimeSeries

APP = Flask(__name__, static_folder="static/", template_folder="static/")
APP.config['SECRET_KEY'] = os.environ.get('SECRET_KEY','')

setup_logger(verbose='DEBUG')
# configure logger
logger.add("app/static/job.log", format="[{level}] {message}", level="DEBUG", colorize=True)

messages = []
threads = []

class Validator:
    def __init__(self, mode, input):
        self.mode = mode
        self.input = input
    def is_valid(self):
        if self.mode == 'coords':
            if type(self.input) != tuple:
                return False
            else:
                try:
                    self.value = SkyCoord(self.input[0], self.input[1])
                except ValueError as e:
                    logger.error(e)
                    return False
                return True

        if type(self.input) == str and self.input.strip() == '':
            return False
        if self.mode == 'position':
            if ":" in self.input or float(self.input):
                self.value = self.input
                return True
            return True
        elif self.mode == 'path':
            self.value = Path(self.input)
            return True
        else:
            return False

# adjusted flask_logger
@logger.catch
def flask_logger():
    """creates logging information"""
    logger.debug(f"Thread count: {len(threads)}")
    if threads:
        current_thread = threads[0]
    else:
        return
    with open("app/static/job.log") as log_info:
        while current_thread.is_alive():
            data = log_info.read()
            msg = "<br/>".join(data.split('\n'))
            yield "data:{}\n\n".format(msg)
            sleep(0.5)
        # Get final messages
        data = log_info.read()
        if "ERROR" in data:
            logger.error("‼️ AstroSource analysis failed")
        else:
            logger.info("✅ AstroSource analysis completed")
        logger.remove()
        yield "data:{}\n\n".format("<br/>".join(data.split('\n')))
        data = log_info.read()
        yield "data:{}\n\n".format("<br/>".join(data.split('\n')))
        open("app/static/job.log", 'w').close()

def thread_function(**kwargs):
    targets = array([(kwargs['ra'], kwargs['dec'], 0, 0)])
    try:
        ts = TimeSeries(targets=targets, **kwargs)
        ts.analyse()
        ts.photometry(filesave=True, targets=targets)
        ts.plot(filesave=True)
    except Exception as e:
        logger.error(e)



@APP.route("/log_stream", methods=["GET"])
def stream():
    """returns logging information"""
    return Response(flask_logger(), mimetype="text/plain", content_type="text/event-stream")


@APP.route("/", methods=["GET","POST"])
def index():
    if request.method == 'POST':
        try:
            ra, dec = convert_coords(request.form['ra'], request.form['dec'])
        except AstrosourceException as e:
            flash(e)
        indir = Validator(mode='path',input=request.form['indir'])

        if not indir.is_valid():
            flash('Directory path is required!')
        else:

            inputs = {
                    'ra':ra,
                    'dec':dec,
                    'indir': indir.value,
                    'matchradius': request.form['matchradius'],
                    'periodlower': -99.9,
                    'periodupper':-99.9,
                    'periodtests':10000,
                    'thresholdcounts': 1000000,
                    'hicounts':3000000,
                    'lowcounts': 5000,
                    'lowestcounts': 1800,
                    'starreject':0.3,
                    'closerejectd': 5.0,
                    'targetradius': 1.5,
                    'matchradius': 1.0,
                    'mincompstars':0.1,
                    'mincompstarstotal': -99,
                    'maxcandidatestars': 10000,
                    'varsearchglobalstdev':-99.9,
                    'varsearchthresh':10000,
                    'varsearchstdev':1.5,
                    'varsearchmagwidth':0.5,
                    'varsearchminimages':0.3,
                    'ignoreedgefraction':0.05,
                    'outliererror':4,
                    'outlierstdev':4,
                    'colourterm':0.0,
                    'colourerror':0.0,
                    'targetcolour':-99.0,
                    'restrictcompcolourcentre':-999.0,
                    'restrictcompcolourrange':-99.0,
                    'restrictmagbrightest':-99.0,
                    'restrictmagdimmest':99.0,
                    'rejectmagbrightest':-99.0,
                    'rejectmagdimmest':99.0
                    }

            asource = threading.Thread(target=thread_function, kwargs=inputs, daemon=True)
            messages.append({'title': "Started astrosource", 'content': f"Working"})
            threads.append(asource)
            asource.start()
            return redirect(url_for('results'))

    return render_template('index.html', messages=messages)

@APP.route("/results", methods=["GET"])
def results():
    """Results and logging page"""
    return render_template("results.html", messages=messages)

if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=5000, threaded=True, debug=True)
