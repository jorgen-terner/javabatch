#!/usr/bin/python
# coding=ISO-8859-1
import getopt
import sys
import json
import time
import requests
import os
import subprocess
import signal
import configparser
import functools
print = functools.partial(print, flush=True)
#
#Viktigt: Glöm inte att meddela AppDrift om förändringer sker i detta skript. De lyfter in skriptet manuellt under en övergångsperiod
#
def help_text():
    print('Script som startar ett batchjobb. Argument som krävs finns beskrivna nedan.')
    print('Mer information går att hitta på https://confluence.sfa.se/display/SOHDLS/Script\n')
    print('Exempel: python springbatch.py -j examplejob.json --start\n')
    print('Tvingande argument:')
    print('-j eller --job                                      (json-fil som pekar ut tjänsterna samt url till miljön)')
    print('')
    print(' --start, --status, --restart, --stop eller --help  (Endast en av dessa krävs')
    print('')
    print('Frivillga argument:')
    print('-a eller --jobargs                               (argument som tjänsten tar emot, i formatet \"key=value\")')
    print('--summary')

def start_job_status(execId, pathstatus, pathsummary, token):
    url = "{}/{}".format(pathstatus, execId.decode('ascii'))

    done = False
    fault = 0
    url.rstrip()
    print(url)
    while not done:
        time.sleep(5)
        response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8', 'FKST': token})
        status = str(response.status_code).encode('utf-8')
        response.encoding='utf-8'
        if (status.startswith(b'2')):
            status_text = response.content.decode('ascii')
            if "COMPLETED" in status_text:
                print(status_text)
                summary_job(execId.decode('ascii'), pathsummary, token)
                prepare_and_run_monitor_script('stop')
                return 0
            elif "STARTED" in status_text:
                print ('Running...')
                pass
            elif "STARTING" in status_text:
                pass
            elif "UNKNOWN" in status_text:
                print(status_text)
                prepare_and_run_monitor_script('error')
                sys.exit(1)
            elif "STOPPED" in status_text:
                print(status_text)
                prepare_and_run_monitor_script('error')
                sys.exit(1)
            elif "FAILED" in status_text:
                print(status_text)
                prepare_and_run_monitor_script('error')
                sys.exit(1)
            else:
                print(status_text)
                prepare_and_run_monitor_script('error')
                sys.exit(1)
        else:
            print(response.content.decode('ascii'))
            if fault == 5:
                prepare_and_run_monitor_script('error')
                sys.exit(1)
            else:
                fault += 1
                pass


def job_status(exec_id, pathstatus, token):
    url = "{}/{}".format(pathstatus, exec_id)

    url.rstrip()
    print(url)

    response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8', 'FKST': token})
    response.encoding='utf-8'
    status = response.content.decode('ascii')
    print(status)
    prepare_and_run_monitor_script('stop')
    return 0

def summary_job(exec_id, pathsummary, token):
    url = "{}/{}".format(pathsummary, str(exec_id))

    url.rstrip()
    print(url)

    response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8',
                                          'FKST': token})
    response.encoding='utf-8'
    summary = response.content
    print(summary.decode('ascii'))
    return 0


def start_job(pathrun, pathstatus, pathsummary, jobargs, token):
    url = "{}/{}".format(pathrun, jobargs)
    url.rstrip()
    print(url)

    response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8', 'FKST': token})
    response.encoding='utf-8'
    status = str(response.status_code).encode('utf-8')
    if (status.startswith(b'2')):
        exec_id = response.content
        print("executionId: " + exec_id.decode('ascii'))
        try:
            subprocess.call(['/openprocess/Automator/PServer/bin/opscmd', 'resval', '-res', 'executionId', '-value', exec_id.decode('ascii')])
        except subprocess.CalledProcessError as e:
            print(e.output)
            print("OP chart parameter executionId not updated, continuing")
        start_job_status(exec_id, pathstatus, pathsummary, token)
    else:
        print(response.content)
        prepare_and_run_monitor_script('error')
        sys.exit(1)


def stop_job(pathstop, jobargs, token):
    url = "{}/{}".format(pathstop, jobargs)
    url.rstrip()
    print(url)

    response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8', 'FKST': token})
    response.encoding='utf-8'
    status = str(response.status_code).encode('utf-8')
    if (status.startswith(b'2')):
        print(response.content.decode('utf-8'))
        prepare_and_run_monitor_script('stop')
        return 0
    else:
        print(response.content.decode('utf-8'))
        prepare_and_run_monitor_script('error')
        sys.exit(1)


def restart_job(pathrestart, jobargs, pathstatus, pathsummary, token):
    url = "{}/{}".format(pathrestart, jobargs)
    url.rstrip()
    print(url)

    response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8', 'FKST': token})
    status = str(response.status_code).encode('utf-8')
    if (status.startswith(b'2')):
        exec_id = response.content
        print("executionId: " + exec_id.decode('utf-8'))
    else:
        print(response.content.decode('utf-8'))
        prepare_and_run_monitor_script('error')
        sys.exit(1)


def jobb_help(pathhelp, token):
    url = pathhelp
    url.rstrip()
    print(url)

    response = requests.get(url, headers={'Content-Type': 'application/json; charset=utf-8', 'FKST': token})
    status = str(response.status_code).encode('utf-8')
    response.encoding='utf-8'
    if (status.startswith(b'2')):
        print(response.content)
        return 0
    else:
        print(response.content)
        sys.exit(1)


def main(argv):

    job = ''
    jobargs = ''
    token = ''
    start = False
    stop = False
    status = False
    restart = False
    summary = False
    help = False
    monitor = ''

    try:
        opts, args = getopt.getopt(argv, "hj:a:t:", ["job=", "jobargs=", "start", "status", "stop", "restart", "summary", "token", "help"])
    except getopt.GetoptError:
        help_text()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            help_text()
            sys.exit()
        elif opt in ("-j", "--job"):
            job = arg
        elif opt in ("-a", "--jobargs"):
            jobargs = arg
        elif opt in ("-t", "--token"):
            token = arg
        elif opt in "--start":
            start = True
        elif opt in "--status":
            status = True
        elif opt in "--stop":
            stop = True
        elif opt in "--restart":
            restart = True
        elif opt in "--summary":
            summary = True
        elif opt in "--help":
            help = True

    if job == '':
        help_text()
        sys.exit(2)

    config = configparser.RawConfigParser()
    config.read(job)

    pathrun = config['endpoints'].get('springbatchpy.v2.start')
    pathstatus = config['endpoints'].get('springbatchpy.v2.status')
    pathstop = config['endpoints'].get('springbatchpy.v2.stop')
    pathrestart = config['endpoints'].get('springbatchpy.v2.restart')
    pathsummary = config['endpoints'].get('springbatchpy.v2.summary')

    try:
        pathhelp = config['endpoints'].get('springbatchpy.v2.help')
    except KeyError as e:
        if help:
            print("Finns ingen hjälptjänst i jsonfilen, avslutar scriptet")
            sys.exit(1)

    print('PID=' + str(os.getpid()))

    if start:
        print("starting job")
        prepare_and_run_monitor_script('start')
        start_job(pathrun, pathstatus, pathsummary, jobargs, token)
    elif stop:
        print("stopping job")
        prepare_and_run_monitor_script('start')
        stop_job(pathstop, jobargs, token)
    elif status:
        print("checking status on job")
        prepare_and_run_monitor_script('start')
        job_status(jobargs, pathstatus, token)
    elif restart:
        print("restarting job")
        prepare_and_run_monitor_script('start')
        restart_job(pathrestart, jobargs, pathrestart, pathsummary, token)
    elif summary:
        print("summary on job")
        summary_job(jobargs, pathsummary, token)
    elif help:
        print("Printing help")
        jobb_help(pathhelp, token)
    else:
        help_text()
        sys.exit(1)

def prepare_and_run_monitor_script(method):
    if os.path.exists("/openprocess/scripts/rfvop/jbatch//monitor_jbatch.sh"):
        call_monitor('/openprocess/scripts/rfvop/jbatch/monitor_jbatch.sh', method)
    else:
        print("Monitor script hittades inte, fortsätter...")


def call_monitor(script_path, method):
    try:
        subprocess.call([script_path, method, str(os.getpid())])
    except subprocess.CalledProcessError as e:
        print(e.output)
        print("Monitor_jbatch did not return 0, continuing")

def sig_handler(signal, handler):
    print("signal " + str(signal) + " detected, exiting gracefully")
    prepare_and_run_monitor_script("error")
    sys.exit(1)


signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGABRT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)

#Dessa går inte att köra på windows, körs det inte i windows så lägger jag även till dessa.
if os.name != 'nt':
    signal.signal(signal.SIGHUP, sig_handler)
    signal.signal(signal.SIGQUIT, sig_handler)
    #signal.signal(signal.SIGCHLD, sig_handler)

if __name__ == "__main__":
    main(sys.argv[1:])
