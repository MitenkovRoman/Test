import sqlite3
import time
import re
import os

def parse_airodump(run_flag,file,db):
    lines = []
    conn = sqlite3.connect(db)
    c = conn.cursor()
    titles = ["(`ID`,`MAC`,`TimeAppend`,`TimeLast`,`Channel`,`Encryption`,`Chipher`,`Auth`,`SignalLevel`,`PacketsCount`,`SSID`)",
        "(`ID`,`MAC`,`TimeAppend`,`TimeLast`,`SignalLevel`,`PacketsCount`,`SSID`)"]
    fields = [[0,1,2,3,5,6,7,8,10,13],[0,1,2,3,4,5]]
    tables = ['AccessPoints', 'Clients']
    while run_flag:
        if not os.path.exists(file):
            print 'File not found!!!'
            time.sleep(2)
            continue

        with open(file) as f:
            lines = f.readlines()
        table = -1
        readtitle = False
        for line in lines:
            if line == '\r\n':
                table += 1
                readtitle = True
            elif readtitle:
                readtitle = False
            else:
                values = line[:-2].replace('\x00','').split(",")
                addvals = []
                for field in fields[table]:
                    addvals.append(values[field])
                sqlstr = 'insert or replace into `'
                sqlstr += tables[table]+'`'+titles[table]
                sqlstr += 'values ((select ID from '+tables[table]+' where `MAC` = "'+values[0]+'"),'+"'"
                sqlstr += "','".join(addvals)
                sqlstr += "')"
                c.execute(sqlstr)
                conn.commit()
    return 0


def follow(thefile):
    while True:
        line = thefile.readline()
        if not line:
            time.sleep(0.5)
            continue
        yield line


def parse_airbase(run_flag):
    pattern = re.compile(r'(d\d:\d\d:\d\d)  Client (\w\w:\w\w:\w\w:\w\w:\w\w:\w\w) associated \((.*)\) to ESSID: "(\w+)"')

    logfile = open("test.log")
    loglines = follow(logfile)
    for line in loglines:
        if not run_flag('emu'):
            return 0
        rez = pattern.match(line)
        if rez:
            print rez.group(1,2,3,4)
