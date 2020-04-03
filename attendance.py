import re
import sys
import logging
import argparse
from typing import Dict,List
from collections import defaultdict

logging.basicConfig()
logger = logging.getLogger(' Attendance')

parser = argparse.ArgumentParser(description='Attendance scoring for Zoom meetings.')
parser.add_argument('zoomfile',metavar='zoomfile',type=str,help='Meeting report from Zoom')
parser.add_argument('roster',metavar='roster',type=str,help='Roster from iGrade')
parser.add_argument('-th',metavar='N',dest='threshhold',default=45,type=int,
        help='Report students attending for less than <N> minutes (exclusive)')
parser.add_argument('--verbose','-v',action='count',default=0,help='Each flag increases verbosity level')
parser.add_argument('--ignore','-i',action='append',help='NetIDs to ignore (typically instruction staff)')
parser.add_argument('--output','-o',dest='output',default='report.csv',
        help='Output file for reporting (matched) students.')

args = parser.parse_args()

loggerLevel = [logging.CRITICAL,logging.ERROR,logging.WARNING,logging.INFO,logging.DEBUG,]
logger.setLevel(loggerLevel[args.verbose])

def parseRoster(fn:str)->Dict[str,int]:
    logger.info('Parsing roster...')
    roster:Dict[str,int] = defaultdict(int)
    with open(fn,'r') as f:
        studentRE = re.compile('\"(\d+)\",\"([\s\w]+)\",\"([\s\w]+)\",\"(\w+)@')
        for line in f.readlines()[1:]:
            student = studentRE.match(line)
            if student:
                roster[student.group(4)]
            else:
                logger.warning(f'Unknown student: {line}')
    return roster

def calculateAttendance(fn:str,roster:Dict[str,int])->Dict[str,int]:
    logger.info('Calculating attendance...')
    unknown:Dict[str,int] = defaultdict(int)
    with open(fn,'r') as f:
        usernameRE = re.compile('(?P<fname>\w+)\s+(?P<lname>\w+)\s*[\[\(]?(?P<netid>\w{3,5}\d{3})?[\]\)]?')
        emailRE = re.compile('(?P<netid>\w+)@ucr.edu')
        for line in f.readlines()[4:]:
            name,email,jt,lt,duration,*_ = line.split(',')
            usernameMatch = usernameRE.match(name)
            netidMatch = emailRE.match(email)
            netid,firstName,lastName = None,None,None
            if usernameMatch:
                netid = usernameMatch.group('netid')
                firstName,lastName = usernameMatch.group('fname'),usernameMatch.group('lname')
            if netidMatch:
                netid = netidMatch.group('netid')
            if netid:
                if netid in roster:
                    roster[netid] += int(duration)
                else:
                    unknown[netid] += int(duration)
            else:
                unknown[name] += int(duration)

    return unknown
        
def attemptMatches(unknown:Dict[str,int],roster:Dict[str,int])->None:
    logger.info('Attempting to match unknown students...')
    nameRE = re.compile('(\w+)\s+(\w+)')
    toRemove:List[str] = []
    for student in unknown:
        if student in roster:
            roster[student] += unknown[student]
        else:
            name = nameRE.match(student)
            if name:
                partial = name.group(1)[0]+name.group(2)[:4]
                possibles = [s for s in roster if s.startswith(partial.lower())]
                if len(possibles) == 1:
                    roster[possibles[0]] += unknown[student]
                    toRemove.append(student)
                else:
                    logger.warning(f'{student} might be: {possibles}')
    for student in toRemove:
        unknown.pop(student)

def report(fn: str,scores:Dict[str,int])->None:
    with open(fn,'w') as f:
        for student in scores:
            f.write(f'{student},{scores[student]}')

if __name__ == '__main__':
    roster = parseRoster(args.roster) #TODO: optional
    unknown = calculateAttendance(args.zoomfile,roster)
    attemptMatches(unknown,roster)
    logger.warning(" Unknown students:")
    allMatched = True
    for student in unknown:
        if not args.ignore or student not in args.ignore:
            allMatched = False
            logger.warning(f' {student}: {unknown[student]}')
    if allMatched:
        logger.warning(' None')
    report(args.output,roster)
