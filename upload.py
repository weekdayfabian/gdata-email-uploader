#!/usr/bin/python

import multiprocessing,Queue,time,os,sys,json,mailbox,getopt,getpass,datetime
from mailbox import Maildir
from gdata.apps.migration import service
from gdata.apps.service import AppsForYourDomainException

# configuration
# Base directory for MailDir structure
# Will have subdirectories domain/user/
baseMailDir = "/var/vmail/"
# where are we storing the mboxes
mboxes = "mboxes/"
# config file
creds = "creds.conf"
# logdir
logdir = "log/"
# logfile
log = "manual-"+str(int(time.time()))+".log"
# parallel processes
procs = 5
# debug output
debug = 0
# when did we start
started = datetime.datetime.now()

def parseConfig():
    conf = {}
    for line in file(creds):
        vals = line.split('=')
        if len(vals) != 2:
            print "error in conf file syntax"
            print line
        else:
            key, val = vals
            conf[key.strip()] = val.strip()
    return conf

def usage():
    print "usage: %s [-v] [-t threads] -u <gmail user> -e <currentemail@domain>" % (sys.argv[0])
    exit(1)

class LogWorker(multiprocessing.Process):
    def __init__(self, logQueue):
        multiprocessing.Process.__init__(self)
        self.logQueue = logQueue
        self.kill_received = False
        self.logfile = open(logdir+log, "w")
    def run(self):
        while not self.kill_received:
            try:
                msg = self.logQueue.get_nowait()
                self.logfile.write(time.ctime() + " " + str(msg) + "\n")
                self.logfile.flush()
                if debug:
                    print msg
            except Queue.Empty:
                time.sleep(1)
        else:
            exit()
    def die(self):
        print "."
        self.kill_received = True

class MboxWorker(multiprocessing.Process):
    def __init__(self, errorQueue, logQueue, luser):
        multiprocessing.Process.__init__(self)
        self.errorQueue = errorQueue
        self.logQueue = logQueue
        self.kill_received = False
    def run(self):
        while not self.kill_received:
            try:
                msg = self.errorQueue.get_nowait()
                reason = msg[0]
                email = msg[1]
                if email[2] == '':
                    mboxFile = luser+"-"+email[1]+"@"+email[0]+"-"+ str(reason) +".mbox"
                else:
                    mboxFile = luser+"-"+email[1]+"@"+email[0]+"-"+email[2]+"-"+ str(reason) +".mbox"
                dest = mailbox.mbox(mboxes+mboxFile)
                dest.lock()
                dest.add(mailbox.mboxMessage(email[5]))
                dest.flush()
                dest.unlock()
                self.logQueue.put("wrote to " + mboxFile + " " + email[3], True, 10)
            except Queue.Empty:
                time.sleep(1)
        else:
            exit()
    def log(self, message):
        print message
    def die(self):
        self.kill_received = True
                
class EmailWorker(multiprocessing.Process):
    def __init__(self, googleCreds, workQueue, logQueue, errorQueue):
        multiprocessing.Process.__init__(self)
        self.googleCreds = googleCreds
        self.workQueue = workQueue
        self.logQueue = logQueue
        self.errorQueue = errorQueue
        self.kill_received = False
        
        # log into google
        self.migServ = service.MigrationService(email=self.googleCreds["username"], 
                password=self.googleCreds["password"], 
                domain=self.googleCreds["domain"], 
                source='fabian-manualmigration-0.2')
        self.migServ.ProgrammaticLogin()
        self.log("logged in as " + googleCreds["username"])

    def run(self):
        # should wait for things in the queue
        while not self.kill_received:
            try:
                email = self.workQueue.get_nowait()
            except Queue.Empty:
                time.sleep(10)
            else:
                code = self.upload(email)
                if code == 503:
                    self.workQueue.put(email)
                    time.sleep(30)
                elif code != None:
                    self.error(code, email)
        else:
            exit()

    def log(self, message):
        self.logQueue.put(message, True, 10)

    def error(self, reason, email):
        msg = (reason, email)
        self.errorQueue.put(msg, True, 10)
        
    def upload(self, email):
        """
        Tuple Structure:
            0   domain
            1   user
            2   folder
            3   eid
            4   msg_flags
            5   msg_text

        Return Codes:
            503     Server Overloaded
        """
        mailProperties = []
        size = int(email[3].split(",")[1].split("=")[1])
        if size > 26214399:
            return "too-big"
        if not 'S' in email[4]:
            mailProperties.append('IS_UNREAD')
        if email[2] == '':
            mailLabels=[]
            mailProperties.append('IS_INBOX')
        else:
            mailLabels=[email[2].replace(".","/")]
        try:
            mailEntry = self.migServ.ImportMail(user_name=email[1],
                mail_message=str(email[5]),
                mail_item_properties=mailProperties,
                mail_labels=mailLabels)
        except AppsForYourDomainException, e:
            err = json.loads(str(e).replace('"',"__@__").replace("'",'"').replace("__@__",'"'))
            if err['status'] != 503:
                self.log(str(e).replace("'",'"') + email[3])
            return err['status']
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            return "unknown-error"
        else:
            if debug:
                sys.stdout.write('.')
                sys.stdout.flush()
    def die(self):
        print "."
        self.kill_received = True                
                
if __name__ == "__main__":

    if len(sys.argv) < 5:
        usage()
        
    try:
        opts, args = getopt.getopt(sys.argv[1:], "u:e:t:hv", ["help"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        
    EMAIL = None
    USER = None
        
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o == "-u":
            USER = a
        elif o == "-e":
            EMAIL = a
        elif o == "-t":
            procs = int(a)
        elif o == "-v":
            debug = 1
            
    if not USER or not EMAIL:
        print "missing user or email param"
        usage()
        
    config = parseConfig()
    if "domain" not in config:
        print "error: no domain in config"
        exit(1)
    if "username" not in config:
        print "error: no username in config"
        exit(1)
    if "password" not in config:
        config["password"] = getpass.getpass()
            
    luser, domain = EMAIL.split("@")
    
    log = USER+"-"+EMAIL+"-"+log
    
    workQueue = multiprocessing.Queue()
    logQueue = multiprocessing.Queue()
    errorQueue = multiprocessing.Queue() 

    # spawn email workers
    workers = []
    for i in range(procs):
        worker = EmailWorker(config, workQueue, logQueue, errorQueue)
        workers.append(worker)
        worker.start()
        
    # spawn log and email writing workers
    logger = LogWorker(logQueue)
    logger.start()
    mboxer = MboxWorker(errorQueue, logQueue, luser)
    mboxer.start()
    
    # load workQueue
    mail = {}
    maildir = Maildir(baseMailDir + domain + "/" + luser, factory=None)
    folders = maildir.list_folders()
    folders.append('') # empty string means INBOX.
    for folder in folders:
        mail[folder] = maildir.get_folder(folder)

    for folder in mail:
        for eid, msg in mail[folder].iteritems():
            #print domain, user, folder, msg.get_flags(), eid, len(str(msg))
            # Process emails here.
            email = (domain,USER,folder,eid,msg.get_flags(),str(msg))
            workQueue.put(email)
        while not workQueue.empty():
            if debug:
                print "workQueue: " + folder + " " + str(workQueue.qsize())
            time.sleep(60)

    logger.put("elapsed time:" + str(datetime.datetime.now() - started))

    # kill ALL the threads!
    for worker in workers:
        worker.terminate()
    logger.terminate()
    mboxer.terminate()
    
    print time.ctime(), "FINISHED all emails"
    print "elapsed time:", datetime.datetime.now() - started
