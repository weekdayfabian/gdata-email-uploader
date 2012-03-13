the ugliest google apps email uploader
--------------------------------------



upload.py: usage: upload.py [-v] [-t threads] -u <gmail user> -e <currentemail@domain>

* -v - verbose mode
* -t x - number of threads (default: 5)
* -u user - gmail user we're uploading to
* -e em@il.com - email address on our current server

reads creds.conf for your credentials

smtpd: no options, run it in screen

creds.conf looks like this:

    username = test@yourdomain.com
    password = password123
    domain   = yourdomain.com

smtpd/smtpd.conf looks like this:

    firstdomain.org
    seconddomain.net
    thirddomain.edu

don't leave any spaces or blank lines in there.
